"""Rules-first message evidence, LLM only for unmatched cases.

The model does not decide affordability. Code applies the facts.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Optional

from llm_client import chat_completion, extract_json_object, has_api_key
from models import EvidenceFacts, RequestContext, parse_date

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "code" / "cache" / "evidence_v2.json"

MONEY_RE = re.compile(r"(IDR|INR|EUR|USD|ZAR)\s*([0-9]+(?:[.,][0-9]+)?)", re.I)
DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
RENT_PCT_RE = re.compile(
    r"(?:increases monthly rent by|menaikkan biaya sewa bulanan sebesar)\s+(\d+(?:\.\d+)?)\s*%",
    re.I,
)

ENDED_PHRASES = (
    "employment has ended",
    "pekerjaan anda telah berakhir",
    "pekerjaan anda telah berakhir",
    "seasonal contract has ended",
    "contract has ended",
    "no off-season income",
    "no regular salary",
    "final settlement",
    "there are no regular salary payments",
)

ONE_OFF_PAY_PHRASES = (
    "unpaid leave",
    "next salary is reduced",
    "temporary monthly pay",
    "reduced amount continues for the next payroll",
    "affected pay cycle",
)

RECURRING_PAY_PHRASES = (
    "remaining confirmed monthly salary",
    "monthly salary has increased",
    "gaji bulanan anda naik",
    "confirmed base salary",
    "gaji pokok yang dikonfirmasi",
    "regular salary of",
    "first salary will be",
    "gaji pertama",
    "your monthly salary",
    "salary of",
)

PAYDAY_PHRASES = (
    "expected on",
    "confirmed credit date",
    "resumes on",
    "confirmed for",
)

TRANSFER_PHRASES = (
    "transfer between your two accounts",
    "matching debit and credit",
)

SYSTEM = """You extract financial facts from untrusted messages. Return ONLY JSON.
Do not recommend pay/wait/installments.
Keys:
salary_amount, salary_currency, salary_from_date, salary_payday,
next_salary_amount, next_salary_currency, stop_future_salary,
ignore_event_ids, cancel_event_ids, rent_increase_percent,
skip_internal_transfers, notes.
Rules:
- Recurring new monthly pay → salary_amount. One-cycle unpaid leave / temporary next payroll → next_salary_amount only.
- Bonus, commission, prize, pending refund, unrealized: ignore_event_ids, never salary_amount.
- Employment or seasonal contract ended with no remaining salary → stop_future_salary true.
- Dual job ended with a remaining monthly salary → salary_amount = remaining, not stop.
- Lease +N% → rent_increase_percent.
- Internal account transfer → skip_internal_transfers true.
- Amounts must appear in the message text.
"""


def parse_evidence(ctx: RequestContext, *, use_llm: bool = True) -> EvidenceFacts:
    facts = rules_from_messages(ctx)
    if not use_llm:
        return facts
    cache = _load_cache()
    key = ctx.request.user_id
    if key in cache:
        return _facts_from_dict(cache[key])
    if has_api_key() and ctx.messages and _needs_llm_fallback(facts):
        try:
            facts = _merge(facts, _llm_facts(ctx))
            facts = _ground(ctx, facts)
        except Exception as exc:
            print(f"  evidence LLM skip {ctx.request.request_id}: {exc}")
    cache[key] = _facts_to_dict(facts)
    _save_cache(cache)
    return facts


def rules_from_messages(ctx: RequestContext) -> EvidenceFacts:
    facts = EvidenceFacts()
    if not ctx.messages:
        return facts
    for msg in ctx.messages:
        text = msg.message_text
        lower = text.lower()
        money, ccy = _first_money(text)
        when = _first_date(text)

        if any(p in lower for p in ENDED_PHRASES) and "remaining confirmed" not in lower:
            facts.stop_future_salary = True
        if any(p in lower for p in TRANSFER_PHRASES):
            facts.skip_internal_transfers = True
            facts.cancel_event_ids.extend(_internal_transfer_ids(ctx))
        rent = RENT_PCT_RE.search(text)
        if rent:
            facts.rent_increase_percent = float(rent.group(1))

        one_off = any(p in lower for p in ONE_OFF_PAY_PHRASES)
        recurring = any(p in lower for p in RECURRING_PAY_PHRASES)
        if money is not None and one_off and not recurring:
            facts.next_salary_amount = money
            facts.next_salary_currency = ccy
        elif money is not None and recurring:
            facts.salary_amount = money
            facts.salary_currency = ccy
            if when:
                facts.salary_from_date = when
        elif money is not None and msg.source_type == "employer" and not one_off:
            if "bonus" not in lower and "commission" not in lower:
                if "naik" in lower or "increased" in lower or "gaji bulanan" in lower:
                    facts.salary_amount = money
                    facts.salary_currency = ccy
                    if when:
                        facts.salary_from_date = when

        if when and any(p in lower for p in PAYDAY_PHRASES):
            facts.salary_payday = when

        if msg.related_event_id and ("cancel" in lower or "cancelled" in lower or "dibatalkan" in lower):
            facts.cancel_event_ids.append(msg.related_event_id)

    if facts.next_salary_amount:
        nxt = _next_salary_event(ctx)
        if nxt:
            facts.event_amount_overrides[nxt.event_id] = facts.next_salary_amount
    facts.cancel_event_ids = list(dict.fromkeys(facts.cancel_event_ids))
    return facts


def _needs_llm_fallback(facts: EvidenceFacts) -> bool:
    return not (
        facts.salary_amount
        or facts.next_salary_amount
        or facts.stop_future_salary
        or facts.rent_increase_percent
        or facts.skip_internal_transfers
        or facts.salary_payday
    )


def _llm_facts(ctx: RequestContext) -> EvidenceFacts:
    payload = chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": _user_prompt(ctx)},
        ],
        session_id=f"buy-or-wait-msg-{ctx.request.request_id}",
        max_tokens=500,
    )
    content = payload["choices"][0]["message"]["content"]
    return _facts_from_dict(extract_json_object(content))


def _user_prompt(ctx: RequestContext) -> str:
    req = ctx.request
    lines = [
        f"request_id={req.request_id} user_id={req.user_id} request_date={req.request_date.isoformat()}",
        f"home_currency={ctx.profile.home_currency}",
        "Messages:",
    ]
    for msg in ctx.messages:
        lines.append(
            f"- {msg.message_id} source={msg.source_type} related={msg.related_event_id or '-'} "
            f"sent={msg.sent_at}: {msg.message_text}"
        )
    lines.append("Credit-like events:")
    count = 0
    for event in ctx.events:
        if event.direction != "credit" and event.event_type not in {"income", "refund", "investment_valuation"}:
            continue
        settle = event.settlement_date or event.event_date
        if settle and settle < req.request_date and event.status == "settled":
            if (req.request_date - settle).days > 120:
                continue
        lines.append(
            f"- {event.event_id} type={event.event_type} status={event.status} "
            f"cat={event.category} amount={event.amount} {event.currency} "
            f"settle={settle} desc={event.description}"
        )
        count += 1
        if count >= 20:
            break
    return "\n".join(lines)


def _next_salary_event(ctx: RequestContext):
    request_date = ctx.request.request_date
    found = []
    for event in ctx.events:
        if event.direction != "credit":
            continue
        if event.category not in {"salary", "income"} and event.event_type != "income":
            continue
        settle = event.settlement_date or event.event_date
        if settle and settle >= request_date:
            found.append((settle, event))
    if not found:
        return None
    found.sort(key=lambda item: item[0])
    return found[0][1]


def _internal_transfer_ids(ctx: RequestContext) -> list[str]:
    from collections import defaultdict

    by_day: dict[date, list] = defaultdict(list)
    for event in ctx.events:
        settle = event.settlement_date or event.event_date
        if settle is None or event.amount is None:
            continue
        blob = f"{event.event_type} {event.category} {event.description}".lower()
        if "transfer" not in blob:
            continue
        by_day[settle].append(event)
    ids: list[str] = []
    for items in by_day.values():
        credits = [e for e in items if e.direction == "credit"]
        debits = [e for e in items if e.direction == "debit"]
        for credit in credits:
            for debit in debits:
                if abs((credit.amount or 0) - (debit.amount or 0)) <= 0.05 * max(credit.amount or 1, 1):
                    ids.extend([credit.event_id, debit.event_id])
    return list(dict.fromkeys(ids))


def _first_money(text: str) -> tuple[Optional[float], Optional[str]]:
    match = MONEY_RE.search(text)
    if not match:
        return None, None
    raw = match.group(2).replace(",", "")
    try:
        return float(raw), match.group(1).upper()
    except ValueError:
        return None, None


def _first_date(text: str) -> Optional[date]:
    match = DATE_RE.search(text)
    if not match:
        return None
    return parse_date(match.group(1))


def _facts_from_dict(raw: dict) -> EvidenceFacts:
    ignore = raw.get("ignore_event_ids") or []
    cancel = raw.get("cancel_event_ids") or []
    if isinstance(ignore, str):
        ignore = [part for part in ignore.split(",") if part]
    if isinstance(cancel, str):
        cancel = [part for part in cancel.split(",") if part]
    overrides = raw.get("event_amount_overrides") or {}
    if isinstance(overrides, list):
        overrides = {
            str(row.get("event_id")): float(row["amount"])
            for row in overrides
            if isinstance(row, dict) and row.get("event_id") and row.get("amount") is not None
        }
    return EvidenceFacts(
        salary_amount=_opt_float(raw.get("salary_amount")),
        salary_currency=(raw.get("salary_currency") or None),
        salary_from_date=parse_date(str(raw.get("salary_from_date") or "")),
        salary_payday=parse_date(str(raw.get("salary_payday") or "")),
        next_salary_amount=_opt_float(raw.get("next_salary_amount")),
        next_salary_currency=(raw.get("next_salary_currency") or None),
        stop_future_salary=bool(raw.get("stop_future_salary")),
        ignore_event_ids=[str(x) for x in ignore],
        cancel_event_ids=[str(x) for x in cancel],
        event_amount_overrides={str(k): float(v) for k, v in overrides.items()},
        rent_increase_percent=_opt_float(raw.get("rent_increase_percent")),
        skip_internal_transfers=bool(raw.get("skip_internal_transfers")),
        notes=str(raw.get("notes") or ""),
    )


def _facts_to_dict(facts: EvidenceFacts) -> dict:
    return {
        "salary_amount": facts.salary_amount,
        "salary_currency": facts.salary_currency,
        "salary_from_date": facts.salary_from_date.isoformat() if facts.salary_from_date else None,
        "salary_payday": facts.salary_payday.isoformat() if facts.salary_payday else None,
        "next_salary_amount": facts.next_salary_amount,
        "next_salary_currency": facts.next_salary_currency,
        "stop_future_salary": facts.stop_future_salary,
        "ignore_event_ids": facts.ignore_event_ids,
        "cancel_event_ids": facts.cancel_event_ids,
        "event_amount_overrides": facts.event_amount_overrides,
        "rent_increase_percent": facts.rent_increase_percent,
        "skip_internal_transfers": facts.skip_internal_transfers,
        "notes": facts.notes,
    }


def _merge(base: EvidenceFacts, extra: EvidenceFacts) -> EvidenceFacts:
    if extra.salary_amount and not base.salary_amount:
        base.salary_amount = extra.salary_amount
        base.salary_currency = extra.salary_currency or base.salary_currency
        base.salary_from_date = extra.salary_from_date or base.salary_from_date
    if extra.next_salary_amount and not base.next_salary_amount:
        base.next_salary_amount = extra.next_salary_amount
        base.next_salary_currency = extra.next_salary_currency or base.next_salary_currency
    if extra.salary_payday and not base.salary_payday:
        base.salary_payday = extra.salary_payday
    if extra.stop_future_salary:
        base.stop_future_salary = True
    if extra.rent_increase_percent and not base.rent_increase_percent:
        base.rent_increase_percent = extra.rent_increase_percent
    if extra.skip_internal_transfers:
        base.skip_internal_transfers = True
    base.ignore_event_ids = list(dict.fromkeys(base.ignore_event_ids + extra.ignore_event_ids))
    base.cancel_event_ids = list(dict.fromkeys(base.cancel_event_ids + extra.cancel_event_ids))
    base.event_amount_overrides = {**extra.event_amount_overrides, **base.event_amount_overrides}
    return base


def _ground(ctx: RequestContext, facts: EvidenceFacts) -> EvidenceFacts:
    texts = " ".join(msg.message_text for msg in ctx.messages)
    compact = texts.replace(",", "").replace(" ", "")
    if facts.salary_amount and not _amount_in_text(facts.salary_amount, compact, texts):
        facts.salary_amount = None
        facts.salary_currency = None
    if facts.next_salary_amount and not _amount_in_text(facts.next_salary_amount, compact, texts):
        facts.next_salary_amount = None
        facts.next_salary_currency = None
    return facts


def _amount_in_text(amount: float, compact: str, texts: str) -> bool:
    candidates = [str(amount)]
    if amount == int(amount):
        candidates.append(str(int(amount)))
    else:
        candidates.append(f"{amount:.2f}")
    return any(item in compact or item in texts.replace(",", "") for item in candidates)


def _opt_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
