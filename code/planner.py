"""Enumerate eligible payment plans and pick the spec-ranked winner."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from forecaster import amount_safe_today, earliest_full_payment, simulate
from models import CashFlow, Decision, PaymentOption, Plan, RequestContext


def decide(ctx: RequestContext) -> Decision:
    request = ctx.request
    profile = ctx.profile
    safe_today = amount_safe_today(ctx)
    earliest = earliest_full_payment(ctx)
    considered = set(profile.payment_methods_user_will_consider)
    plans: list[Plan] = []

    plans.extend(_full_payment_plans(ctx, considered, earliest))
    plans.extend(_partial_plans(ctx, considered, safe_today, earliest))
    plans.extend(_installment_plans(ctx, considered))
    plans.extend(_wait_plans(ctx, considered, earliest))

    if not plans:
        plans.extend(_spending_change_full(ctx, considered))

    ranked = [plan for plan in plans if plan.method]
    if not ranked:
        return _not_recommended(ctx, safe_today, earliest)

    winner = min(ranked, key=lambda plan: _rank_key(plan, request.desired_completion_date))
    return _to_decision(ctx, winner, safe_today, earliest)


def _full_payment_plans(
    ctx: RequestContext, considered: set[str], earliest: Optional[date]
) -> list[Plan]:
    if "full_payment" not in considered:
        return []
    request = ctx.request
    ok, _ = simulate(ctx, extra_debits=[(request.request_date, request.requested_amount)])
    if not ok:
        return []
    return [
        Plan(
            method="full_payment",
            payments=[(request.request_date, request.requested_amount)],
            spending_changes=[],
            total_paid=request.requested_amount,
            status="affordable_now" if earliest == request.request_date else "affordable_with_plan",
        )
    ]


def _partial_plans(
    ctx: RequestContext,
    considered: set[str],
    safe_today: float,
    earliest: Optional[date],
) -> list[Plan]:
    request = ctx.request
    if "partial_payment" not in considered:
        return []
    if not request.allows_partial_payment:
        return []
    if earliest is None or earliest > request.desired_completion_date:
        return []
    if not (0 < safe_today < request.requested_amount):
        return []
    remainder = round(request.requested_amount - safe_today, 2)
    payments = [(request.request_date, safe_today), (earliest, remainder)]
    ok, _ = simulate(ctx, extra_debits=payments)
    if not ok:
        return []
    return [
        Plan(
            method="partial_payment",
            payments=payments,
            spending_changes=[],
            total_paid=request.requested_amount,
            status="affordable_with_plan",
        )
    ]


def _installment_plans(ctx: RequestContext, considered: set[str]) -> list[Plan]:
    if "installments" not in considered:
        return []
    max_months = ctx.profile.max_installment_months
    plans: list[Plan] = []
    for option in ctx.options:
        if option.payment_method != "installments":
            continue
        if max_months is None:
            continue
        months = _option_months(option)
        if months is not None and months > max_months:
            continue
        payments = _option_schedule(option)
        if not payments:
            continue
        if payments[-1][0] > ctx.request.desired_completion_date:
            # still eligible if it is the only way, but ranking prefers deadline
            pass
        ok, _ = simulate(ctx, extra_debits=payments)
        if not ok:
            continue
        plans.append(
            Plan(
                method="installments",
                payments=payments,
                spending_changes=[],
                total_paid=option.total_payable_amount,
                option_id=option.payment_option_id,
                status="affordable_with_plan",
            )
        )
    return plans


def _wait_plans(
    ctx: RequestContext, considered: set[str], earliest: Optional[date]
) -> list[Plan]:
    if "full_payment" not in considered:
        return []
    if earliest is None or earliest <= ctx.request.request_date:
        return []
    if earliest > ctx.request.desired_completion_date:
        return []
    payments = [(earliest, ctx.request.requested_amount)]
    ok, _ = simulate(ctx, extra_debits=payments)
    if not ok:
        return []
    status = (
        "affordable_later"
        if earliest <= ctx.request.desired_completion_date
        else "affordable_later"
    )
    return [
        Plan(
            method="wait",
            payments=payments,
            spending_changes=[],
            total_paid=ctx.request.requested_amount,
            status=status,
        )
    ]


def _spending_change_full(ctx: RequestContext, considered: set[str]) -> list[Plan]:
    if "full_payment" not in considered:
        return []
    request = ctx.request
    candidates = _change_candidates(ctx)
    if not candidates:
        return []
    # Try stopping largest stoppable series first, then reductions.
    stopped: set[str] = set()
    reduced: dict[str, float] = {}
    changes: list[str] = []
    for kind, flow in candidates:
        if len(changes) >= 3:
            break
        if kind == "stop":
            trial_stop = set(stopped) | {flow.event_id.split(":proj:")[0]}
            ok, _ = simulate(
                ctx,
                extra_debits=[(request.request_date, request.requested_amount)],
                stopped_event_ids=trial_stop,
                reduced=reduced,
            )
            stopped = trial_stop
            changes.append(f"stop:{flow.event_id.split(':proj:')[0]}")
            if ok:
                break
        elif kind == "reduce" and flow.minimum_allowed_amount is not None:
            base = flow.event_id.split(":proj:")[0]
            trial_reduced = dict(reduced)
            trial_reduced[base] = flow.minimum_allowed_amount
            ok, _ = simulate(
                ctx,
                extra_debits=[(request.request_date, request.requested_amount)],
                stopped_event_ids=stopped,
                reduced=trial_reduced,
            )
            reduced = trial_reduced
            changes.append(
                f"reduce_to:{base}:{_fmt_amount(flow.minimum_allowed_amount)}"
            )
            if ok:
                break

    if not changes:
        return []
    ok, _ = simulate(
        ctx,
        extra_debits=[(request.request_date, request.requested_amount)],
        stopped_event_ids=stopped,
        reduced=reduced,
    )
    if not ok:
        return []
    return [
        Plan(
            method="full_payment",
            payments=[(request.request_date, request.requested_amount)],
            spending_changes=changes[:3],
            total_paid=request.requested_amount,
            status="affordable_with_plan",
        )
    ]


def _change_candidates(ctx: RequestContext) -> list[tuple[str, CashFlow]]:
    seen: set[str] = set()
    stoppable: list[CashFlow] = []
    reducible: list[CashFlow] = []
    for flow in ctx.cashflows:
        if flow.amount >= 0:
            continue
        base = flow.event_id.split(":proj:")[0]
        if base in seen:
            continue
        seen.add(base)
        if flow.stoppable:
            stoppable.append(flow)
        elif flow.reducible and flow.minimum_allowed_amount is not None:
            reducible.append(flow)
    stoppable.sort(key=lambda f: abs(f.amount), reverse=True)
    reducible.sort(key=lambda f: abs(f.amount) - (f.minimum_allowed_amount or 0), reverse=True)
    return [("stop", f) for f in stoppable] + [("reduce", f) for f in reducible]


def _option_schedule(option: PaymentOption) -> list[tuple[date, float]]:
    if option.first_payment_date is None or option.number_of_payments <= 0:
        return []
    freq = option.payment_frequency_days or 0
    payments = []
    for i in range(option.number_of_payments):
        day = option.first_payment_date + timedelta(days=freq * i)
        payments.append((day, option.payment_amount))
    return payments


def _option_months(option: PaymentOption) -> Optional[int]:
    if option.number_of_payments <= 0:
        return None
    freq = option.payment_frequency_days or 30
    if freq >= 26:
        return option.number_of_payments
    return max(1, int((option.number_of_payments * freq + 29) / 30))


def _rank_key(plan: Plan, deadline: date) -> tuple:
    completes = 0 if plan.last_date and plan.last_date <= deadline else 1
    changes = 0 if not plan.spending_changes else 1
    start = plan.start_date or date.max
    n_pay = len(plan.payments) if plan.payments else 99
    option_num = int("".join(ch for ch in plan.option_id if ch.isdigit()) or "999999")
    return (completes, changes, plan.total_paid, start, n_pay, option_num)


def _not_recommended(ctx: RequestContext, safe_today: float, earliest: Optional[date]) -> Decision:
    return Decision(
        request_id=ctx.request.request_id,
        amount_safe_to_pay=safe_today,
        affordability_status="not_affordable",
        recommended_payment_method="not_recommended",
        payment_plan="none",
        earliest_date_for_full_payment=earliest.isoformat() if earliest else "",
        spending_changes_needed="none",
        decision_explanation=_explain_not_recommended(ctx, safe_today),
    )


def _to_decision(
    ctx: RequestContext, plan: Plan, safe_today: float, earliest: Optional[date]
) -> Decision:
    request = ctx.request
    status = plan.status
    if plan.method == "full_payment" and not plan.spending_changes:
        if earliest == request.request_date:
            status = "affordable_now"
        elif plan.spending_changes:
            status = "affordable_with_plan"
    if plan.method == "wait":
        status = "affordable_later"
    earliest_str = earliest.isoformat() if earliest else ""
    if status == "affordable_now":
        earliest_str = request.request_date.isoformat()
    return Decision(
        request_id=request.request_id,
        amount_safe_to_pay=safe_today,
        affordability_status=status,
        recommended_payment_method=plan.method,
        payment_plan=_format_plan(plan),
        earliest_date_for_full_payment=earliest_str,
        spending_changes_needed="|".join(plan.spending_changes) if plan.spending_changes else "none",
        decision_explanation=_explain(ctx, plan),
    )


def _format_plan(plan: Plan) -> str:
    if not plan.payments:
        return "none"
    return "|".join(f"{day.isoformat()}:{_fmt_amount(amount)}" for day, amount in plan.payments)


def _fmt_amount(value: float) -> str:
    value = round(value + 1e-9, 2)
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    text = f"{value:.2f}"
    return text


def _explain(ctx: RequestContext, plan: Plan) -> str:
    ccy = ctx.profile.home_currency
    floor = _fmt_amount(ctx.profile.minimum_balance_to_keep)
    amount = _fmt_amount(ctx.request.requested_amount)
    if plan.method == "full_payment" and not plan.spending_changes:
        return (
            f"Pay {ccy} {amount} today. This leaves at least {ccy} {floor} "
            f"available over the next 90 days."
        )
    if plan.method == "full_payment" and plan.spending_changes:
        return (
            f"Adjust flexible spending ({'|'.join(plan.spending_changes)}), then pay "
            f"{ccy} {amount} today. This leaves at least {ccy} {floor} available."
        )
    if plan.method == "installments":
        n = len(plan.payments)
        each = _fmt_amount(plan.payments[0][1])
        start = plan.payments[0][0].strftime("%-d %B %Y") if plan.payments else ""
        return (
            f"Use {n} installments of {ccy} {each}, starting {start}. "
            f"This leaves at least {ccy} {floor} available."
        )
    if plan.method == "partial_payment":
        first = _fmt_amount(plan.payments[0][1])
        second = _fmt_amount(plan.payments[1][1])
        day = plan.payments[1][0].strftime("%-d %B %Y")
        return (
            f"Pay {ccy} {first} today and the remaining {ccy} {second} on {day}. "
            f"This completes the full request and keeps the {ccy} {floor} minimum protected."
        )
    if plan.method == "wait":
        day = plan.payments[0][0].strftime("%-d %B %Y")
        return (
            f"Wait until {day}, then pay {ccy} {amount} in full. "
            f"Paying sooner would put the {ccy} {floor} minimum at risk."
        )
    return _explain_not_recommended(ctx, amount_safe_today(ctx))


def _explain_not_recommended(ctx: RequestContext, safe_today: float) -> str:
    ccy = ctx.profile.home_currency
    floor = _fmt_amount(ctx.profile.minimum_balance_to_keep)
    deadline = ctx.request.desired_completion_date.strftime("%-d %B %Y")
    requested = _fmt_amount(ctx.request.requested_amount)
    if safe_today > 0:
        return (
            f"Do not proceed with the {ccy} {requested} request. Although "
            f"{ccy} {_fmt_amount(safe_today)} is available today, the full amount cannot "
            f"be completed safely within 90 days."
        )
    return (
        f"Do not make this payment by {deadline}. None of the available options "
        f"keeps the {ccy} {floor} minimum protected."
    )
