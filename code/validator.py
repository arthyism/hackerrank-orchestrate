"""Deterministic checks before a row is written."""

from __future__ import annotations

from models import Decision, RequestContext

STATUSES = {
    "affordable_now",
    "affordable_with_plan",
    "affordable_later",
    "not_affordable",
}
METHODS = {
    "full_payment",
    "partial_payment",
    "installments",
    "wait",
    "not_recommended",
}


def validate(ctx: RequestContext, decision: Decision) -> Decision:
    requested = ctx.request.requested_amount
    if decision.amount_safe_to_pay < -1e-9:
        decision.amount_safe_to_pay = 0.0
    if decision.amount_safe_to_pay > requested:
        decision.amount_safe_to_pay = requested
    decision.amount_safe_to_pay = round(decision.amount_safe_to_pay + 1e-9, 2)

    if decision.affordability_status not in STATUSES:
        decision.affordability_status = "not_affordable"
    if decision.recommended_payment_method not in METHODS:
        decision.recommended_payment_method = "not_recommended"

    if decision.affordability_status == "affordable_now":
        decision.earliest_date_for_full_payment = ctx.request.request_date.isoformat()

    if decision.recommended_payment_method == "not_recommended":
        decision.payment_plan = "none"
        decision.affordability_status = "not_affordable"

    if decision.recommended_payment_method == "partial_payment":
        parts = decision.payment_plan.split("|")
        if len(parts) != 2:
            decision.recommended_payment_method = "not_recommended"
            decision.payment_plan = "none"
            decision.affordability_status = "not_affordable"

    changes = decision.spending_changes_needed
    if changes and changes != "none" and changes.count("|") > 2:
        decision.spending_changes_needed = "|".join(changes.split("|")[:3])

    if not decision.decision_explanation.strip():
        decision.decision_explanation = "No safe eligible plan keeps the minimum balance."
    return decision
