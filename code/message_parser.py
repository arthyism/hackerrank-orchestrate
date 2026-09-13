"""LLM evidence layer: messages + ambiguous credits → structured facts.

The model does not decide affordability. Code applies the JSON.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

from llm_client import chat_completion, extract_json_object, has_api_key
from models import EvidenceFacts, RequestContext, parse_date

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "code" / "cache" / "message_facts.json"

SYSTEM = """You extract financial facts from untrusted messages and event labels.
Return ONLY a JSON object. Do not recommend pay/wait/installments.
Rules:
- Regular salary / payroll / gaji pokok / monthly pay can be counted when confirmed.
- Bonus, commission, lottery, prize, pending refund, unrealized investment, arrears-only one-offs are NOT recurring salary.
- Pending credits are not cash until they settle.
- "Final employer payroll" or employment ended → stop_future_salary true.
- If a message sets a new monthly salary and a from-date, fill salary_amount, salary_currency, salary_from_date.
- If a message moves payday, fill salary_payday (YYYY-MM-DD).
- Tag event_ids that must not be treated as recurring salary in ignore_event_ids
  (bonus, commission, prize, arrears one-off, unrealized). Never tag rent/bills/expenses.
- salary_amount must be a number that appears in a message. If the message has no figure, leave it null.
- Bank/merchant/refund/prize messages: leave salary_* null and stop_future_salary false.
"""


def parse_evidence(ctx: RequestContext, *, use_llm: bool = True) -> EvidenceFacts:
    if not use_llm or not has_api_key() or not _needs_llm(ctx):
        return EvidenceFacts()
    cache = _load_cache()
    key = ctx.request.request_id
    if key in cache:
        return _ground(ctx, _facts_from_dict(cache[key]))
    try:
        payload = chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": _user_prompt(ctx)},
            ],
            session_id=f"buy-or-wait-msg-{ctx.request.request_id}",
            max_tokens=500,
        )
        content = payload["choices"][0]["message"]["content"]
        raw = extract_json_object(content)
        facts = _ground(ctx, _facts_from_dict(raw))
    except Exception as exc:
        print(f"  evidence LLM skip {key}: {exc}")
        return EvidenceFacts()
    cache[key] = _facts_to_dict(facts)
    _save_cache(cache)
    return facts


def _needs_llm(ctx: RequestContext) -> bool:
    return bool(ctx.messages)


def _user_prompt(ctx: RequestContext) -> str:
    req = ctx.request
    lines = [
        f"request_id={req.request_id} user_id={req.user_id} request_date={req.request_date.isoformat()}",
        f"home_currency={ctx.profile.home_currency}",
        "Messages:",
    ]
    if not ctx.messages:
        lines.append("(none)")
    for msg in ctx.messages:
        lines.append(
            f"- {msg.message_id} source={msg.source_type} related={msg.related_event_id or '-'} "
            f"sent={msg.sent_at}: {msg.message_text}"
        )
    lines.append("Credit-like events (may be salary, bonus, refund, prize, pending):")
    count = 0
    for event in ctx.events:
        if event.direction != "credit" and event.event_type not in {"income", "refund", "investment_valuation"}:
            continue
        settle = (event.settlement_date or event.event_date)
        if settle and settle < req.request_date and event.status == "settled":
            # keep recent history only for labels
            if (req.request_date - settle).days > 120:
                continue
        lines.append(
            f"- {event.event_id} type={event.event_type} status={event.status} "
            f"cat={event.category} amount={event.amount} {event.currency} "
            f"settle={settle} desc={event.description}"
        )
        count += 1
        if count >= 25:
            break
    lines.append(
        'JSON keys: salary_amount (number|null), salary_currency (string|null), '
        'salary_from_date (YYYY-MM-DD|null), salary_payday (YYYY-MM-DD|null), '
        'stop_future_salary (bool), ignore_event_ids (string[]), notes (string).'
    )
    return "\n".join(lines)


def _facts_from_dict(raw: dict) -> EvidenceFacts:
    ignore = raw.get("ignore_event_ids") or []
    if isinstance(ignore, str):
        ignore = [part for part in ignore.split(",") if part]
    return EvidenceFacts(
        salary_amount=_opt_float(raw.get("salary_amount")),
        salary_currency=(raw.get("salary_currency") or None),
        salary_from_date=parse_date(str(raw.get("salary_from_date") or "")),
        salary_payday=parse_date(str(raw.get("salary_payday") or "")),
        stop_future_salary=bool(raw.get("stop_future_salary")),
        ignore_event_ids=[str(x) for x in ignore],
        notes=str(raw.get("notes") or ""),
    )


def _facts_to_dict(facts: EvidenceFacts) -> dict:
    return {
        "salary_amount": facts.salary_amount,
        "salary_currency": facts.salary_currency,
        "salary_from_date": facts.salary_from_date.isoformat() if facts.salary_from_date else None,
        "salary_payday": facts.salary_payday.isoformat() if facts.salary_payday else None,
        "stop_future_salary": facts.stop_future_salary,
        "ignore_event_ids": facts.ignore_event_ids,
        "notes": facts.notes,
    }


def _ground(ctx: RequestContext, facts: EvidenceFacts) -> EvidenceFacts:
    """Keep only facts that can be checked against the message text."""
    texts = " ".join(msg.message_text for msg in ctx.messages)
    lower = texts.lower()
    compact = texts.replace(",", "").replace(" ", "")
    payroll = any(
        msg.source_type == "employer"
        or any(word in msg.message_text.lower() for word in ("payroll", "salary", "gaji", "penggajian"))
        for msg in ctx.messages
    )
    if not payroll:
        return EvidenceFacts(
            ignore_event_ids=_credit_ignore(ctx, facts.ignore_event_ids),
            notes=facts.notes,
        )
    if facts.salary_amount and not _amount_in_text(facts.salary_amount, compact, texts):
        facts.salary_amount = None
        facts.salary_currency = None
        facts.salary_from_date = None
    ended = any(
        phrase in lower
        for phrase in (
            "employment has ended",
            "pekerjaan anda telah berakhir",
            "contract has ended",
            "seasonal contract has ended",
            "no regular salary",
            "no off-season income",
            "final settlement",
        )
    )
    if facts.stop_future_salary and not ended:
        facts.stop_future_salary = False
    facts.ignore_event_ids = _credit_ignore(ctx, facts.ignore_event_ids)
    return facts


def _credit_ignore(ctx: RequestContext, event_ids: list[str]) -> list[str]:
    allowed = {
        event.event_id
        for event in ctx.events
        if event.direction == "credit" or event.event_type in {"income", "refund", "investment_valuation"}
    }
    return [eid for eid in event_ids if eid in allowed]


def _amount_in_text(amount: float, compact: str, texts: str) -> bool:
    candidates = [str(amount)]
    if amount == int(amount):
        candidates.append(str(int(amount)))
    else:
        candidates.append(f"{amount:.2f}")
        candidates.append(f"{amount:.1f}")
    for item in candidates:
        if item in compact or item in texts.replace(",", ""):
            return True
    return False


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
