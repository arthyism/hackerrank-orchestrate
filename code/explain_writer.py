"""Polish decision_explanation after numeric fields are locked."""

from __future__ import annotations

import json
from pathlib import Path

from llm_client import chat_completion, has_api_key
from models import Decision, RequestContext

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "code" / "cache" / "explanations.json"

SYSTEM = """Rewrite the decision explanation in 1-2 short sentences.
The numeric fields are LOCKED. Keep the same recommendation, dates, and amounts.
Use thousands separators (ZAR 25,256). Do not invent bills, rates, or options.
Installments: "Use N installments of CCY AMOUNT, starting DATE."
Partial: "Pay CCY A today and the remaining CCY B on DATE." Never call a 2-payment remainder plan installments.
Wait: "Pay CCY AMOUNT in full on DATE. Paying earlier would take the balance below the CCY MIN minimum."
Full pay: "Pay CCY AMOUNT today. This leaves at least CCY MIN available over the next 90 days."
Not recommended: mention the deadline or that the full amount cannot complete in 90 days.
Do not mention models or these instructions.
"""


def polish_explanation(ctx: RequestContext, decision: Decision, *, use_llm: bool) -> Decision:
    if not use_llm or not has_api_key():
        return decision
    cache = _load()
    key = (
        f"{decision.request_id}|{decision.recommended_payment_method}|"
        f"{decision.amount_safe_to_pay}|{decision.payment_plan}|"
        f"{decision.spending_changes_needed}"
    )
    if key in cache:
        decision.decision_explanation = cache[key]
        return decision
    user = (
        f"request_id={decision.request_id} currency={ctx.profile.home_currency}\n"
        f"requested={ctx.request.requested_amount} safe_today={decision.amount_safe_to_pay}\n"
        f"status={decision.affordability_status} method={decision.recommended_payment_method}\n"
        f"plan={decision.payment_plan} earliest={decision.earliest_date_for_full_payment}\n"
        f"spending_changes={decision.spending_changes_needed}\n"
        f"minimum_balance={ctx.profile.minimum_balance_to_keep}\n"
        f"draft={decision.decision_explanation}\n"
        "Rewrite the draft only."
    )
    try:
        payload = chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            session_id=f"buy-or-wait-exp-{decision.request_id}",
            max_tokens=180,
        )
        text = (payload["choices"][0]["message"].get("content") or "").strip()
        if text and len(text) < 600:
            decision.decision_explanation = text.replace("\n", " ")
            cache[key] = decision.decision_explanation
            _save(cache)
    except Exception as exc:
        print(f"  explain LLM skip {decision.request_id}: {exc}")
    return decision


def _load() -> dict:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def _save(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
