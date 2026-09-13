"""Turn a user's events into dated home-currency cash flows."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import median
from typing import Optional

from data_loader import Dataset
from models import CashFlow, Event, RequestContext

IGNORE_STATUS = {"cancelled", "failed", "unrealized"}
IGNORE_TYPES = {"investment_valuation"}
CREDIT_PENDING_SKIP = True
FORECAST_DAYS = 90


def build_cashflows(dataset: Dataset, ctx: RequestContext) -> list[CashFlow]:
    profile = ctx.profile
    request_date = ctx.request.request_date
    horizon = request_date + timedelta(days=FORECAST_DAYS)
    flows: list[CashFlow] = []
    covered: set[tuple[str, date]] = set()

    for event in ctx.events:
        if event.status in IGNORE_STATUS or event.event_type in IGNORE_TYPES:
            continue
        if event.direction == "non_cash":
            continue
        settle = event.settlement_date or event.event_date
        if settle is None:
            continue
        if settle < request_date:
            continue
        if settle > horizon:
            continue
        if event.direction == "credit" and event.status == "pending":
            continue
        if event.amount is None:
            override = ctx.amount_overrides.get(event.event_id)
            if override is None:
                continue
            amount = override
        else:
            amount = event.amount
        home_amount = dataset.convert(
            amount, event.currency, profile.home_currency, settle.isoformat()
        )
        signed = home_amount if event.direction == "credit" else -home_amount
        essential = _is_essential(ctx, event)
        flow = CashFlow(
            on_date=settle,
            amount=signed,
            event_id=event.event_id,
            series_key=_series_key(event),
            category=event.category,
            essential=essential,
            source="explicit",
            stoppable=_can_stop(ctx, event),
            reducible=_can_reduce(ctx, event),
            original_amount=abs(signed),
            minimum_allowed_amount=_min_allowed_home(dataset, ctx, event, settle),
            description=event.description,
        )
        flows.append(flow)
        covered.add((flow.series_key, settle))

    flows.extend(_project_recurring(dataset, ctx, covered, request_date, horizon))
    flows.sort(key=lambda item: (item.on_date, item.event_id))
    ctx.cashflows = flows
    return flows


def _series_key(event: Event) -> str:
    return f"{event.event_type}|{event.category}|{event.description}"


def _is_essential(ctx: RequestContext, event: Event) -> bool:
    if event.category in ctx.profile.expense_categories_to_protect:
        return True
    if event.event_type in {"debt_payment"}:
        return True
    if event.flexibility == "fixed" and event.direction == "debit":
        if event.category in {"rent", "housing", "utilities", "groceries", "education"}:
            return True
    return False


def _can_stop(ctx: RequestContext, event: Event) -> bool:
    if event.flexibility not in {"stoppable", "reducible_or_stoppable"}:
        return False
    return event.category in ctx.profile.expense_categories_user_is_willing_to_stop


def _can_reduce(ctx: RequestContext, event: Event) -> bool:
    if event.flexibility not in {"reducible", "reducible_or_stoppable"}:
        return False
    return event.category in ctx.profile.expense_categories_user_is_willing_to_reduce


def _min_allowed_home(
    dataset: Dataset, ctx: RequestContext, event: Event, settle: date
) -> Optional[float]:
    if event.minimum_allowed_amount is None:
        return None
    return dataset.convert(
        event.minimum_allowed_amount,
        event.currency,
        ctx.profile.home_currency,
        settle.isoformat(),
    )


VARIABLE_CATEGORIES = {
    "groceries",
    "dining",
    "transport",
    "shopping",
    "entertainment",
}


def _project_recurring(
    dataset: Dataset,
    ctx: RequestContext,
    covered: set[tuple[str, date]],
    request_date: date,
    horizon: date,
) -> list[CashFlow]:
    history: dict[str, list[Event]] = defaultdict(list)
    for event in ctx.events:
        if event.status != "settled":
            continue
        if event.direction == "non_cash" or event.event_type in IGNORE_TYPES:
            continue
        settle = event.settlement_date or event.event_date
        if settle is None or settle >= request_date:
            continue
        if event.amount is None:
            continue
        history[_series_key(event)].append(event)

    projected: list[CashFlow] = []
    projected.extend(_project_salary(dataset, ctx, covered, request_date, horizon))
    projected.extend(_project_variable_categories(dataset, ctx, request_date, horizon))
    for key, items in history.items():
        sample = items[0]
        if sample.category in VARIABLE_CATEGORIES:
            continue
        items.sort(key=lambda e: e.settlement_date or e.event_date)
        if len(items) < 3:
            continue
        dates = [e.settlement_date or e.event_date for e in items]
        gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
        if not gaps:
            continue
        gap = int(round(median(gaps)))
        if not (26 <= gap <= 35 or 85 <= gap <= 95):
            continue
        last = items[-1]
        if last.direction == "credit":
            continue
        amounts = []
        for event in items[-6:]:
            settle = event.settlement_date or event.event_date
            home = dataset.convert(
                event.amount, event.currency, ctx.profile.home_currency, settle.isoformat()
            )
            amounts.append(home)
        conservative = amounts[-1]
        cursor = dates[-1] + timedelta(days=gap)
        series_index = 0
        while cursor <= horizon:
            if cursor >= request_date and (key, cursor) not in covered:
                nearby = any(abs((cursor - day).days) <= 3 and sk == key for sk, day in covered)
                if not nearby:
                    signed = conservative if last.direction == "credit" else -conservative
                    projected.append(
                        CashFlow(
                            on_date=cursor,
                            amount=signed,
                            event_id=f"{last.event_id}:proj:{series_index}",
                            series_key=key,
                            category=last.category,
                            essential=_is_essential(ctx, last),
                            source="projected",
                            stoppable=_can_stop(ctx, last),
                            reducible=_can_reduce(ctx, last),
                            original_amount=abs(signed),
                            minimum_allowed_amount=_min_allowed_home(
                                dataset, ctx, last, cursor
                            ),
                            description=last.description,
                        )
                    )
            cursor += timedelta(days=gap)
            series_index += 1
    return projected


def _is_final_payroll(event: Event) -> bool:
    text = event.description.lower()
    return "final employer" in text or "final payroll" in text or "last employer payroll" in text


def _is_salary_event(event: Event) -> bool:
    if event.direction != "credit":
        return False
    if event.event_type == "refund":
        return False
    desc = event.description.lower()
    if any(
        word in desc
        for word in (
            "bonus",
            "commission",
            "lottery",
            "refund",
            "prize",
            "arrears",
            "one-time",
            "one time",
            "adjustment",
        )
    ):
        return False
    return event.category in {"salary", "income"} or event.event_type == "income"


def _project_salary(
    dataset: Dataset,
    ctx: RequestContext,
    covered: set[tuple[str, date]],
    request_date: date,
    horizon: date,
) -> list[CashFlow]:
    """Repeat confirmed salary. Do not invent pay after a final payroll."""
    facts = ctx.evidence
    if facts and facts.stop_future_salary:
        return []
    salaries = [
        event
        for event in ctx.events
        if _is_salary_event(event)
        and event.status not in IGNORE_STATUS
        and event.status != "pending"
        and (event.settlement_date or event.event_date)
        and event.amount is not None
        and not (facts and event.event_id in facts.ignore_event_ids)
    ]
    if facts and facts.salary_amount and facts.salary_amount > 0 and ctx.messages:
        from_date = facts.salary_from_date or facts.salary_payday or request_date
        ccy = facts.salary_currency or ctx.profile.home_currency
        amount_home = dataset.convert(
            facts.salary_amount, ccy, ctx.profile.home_currency, from_date.isoformat()
        )
        anchor = facts.salary_payday or from_date
        return _salary_series(amount_home, anchor, covered, request_date, horizon, "evidence")
    if not salaries:
        return []
    salaries.sort(key=lambda e: e.settlement_date or e.event_date)
    last = salaries[-1]
    if _is_final_payroll(last):
        return []

    scheduled = [e for e in salaries if e.status == "scheduled"]
    settled = [e for e in salaries if e.status == "settled" and "prorated" not in e.description.lower()]
    source = scheduled[-1] if scheduled else (settled[-1] if settled else last)
    amount_home = dataset.convert(
        source.amount,
        source.currency,
        ctx.profile.home_currency,
        (source.settlement_date or source.event_date).isoformat(),
    )
    anchor = facts.salary_payday if facts and facts.salary_payday else (
        source.settlement_date or source.event_date
    )
    return _salary_series(amount_home, anchor, covered, request_date, horizon, source.event_id)


def _salary_series(
    amount_home: float,
    anchor: date,
    covered: set[tuple[str, date]],
    request_date: date,
    horizon: date,
    source_id: str,
) -> list[CashFlow]:
    cursor = anchor
    if cursor < request_date:
        while cursor < request_date:
            cursor = _add_months(cursor, 1)
    projected: list[CashFlow] = []
    index = 0
    key = "income|salary|confirmed"
    while cursor <= horizon:
        nearby_explicit = any(
            abs((cursor - day).days) <= 3 and "salary" in sk for sk, day in covered
        )
        if cursor >= request_date and not nearby_explicit:
            projected.append(
                CashFlow(
                    on_date=cursor,
                    amount=amount_home,
                    event_id=f"{source_id}:salary:{index}",
                    series_key=key,
                    category="salary",
                    essential=False,
                    source="projected",
                    original_amount=amount_home,
                    description="confirmed salary",
                )
            )
        cursor = _add_months(cursor, 1)
        index += 1
    return projected


def _add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    cap = [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(day.day, cap))


def _next_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def _days_in_month(day: date) -> int:
    start = day.replace(day=1)
    return (_next_month(start) - start).days


def _variable_envelope(totals: list[float]) -> float:
    """One complete month of a habit. Need 2+ months or it is a one-off."""
    if len(totals) < 2:
        return 0.0
    recent = totals[-3:]
    return float(median(recent))


def _project_variable_categories(
    dataset: Dataset, ctx: RequestContext, request_date: date, horizon: date
) -> list[CashFlow]:
    """Repeat grocery/dining/transport/etc. as monthly envelopes.

    Repeat vs one-off is deterministic: a category with only one observed
    month is not a habit. LLM is not used here — cadence is in the ledger.
    Also reserve the unused fraction of the current month (the main
    amount_safe_to_pay leak: we used to start only next calendar month).
    """
    by_cat_month: dict[tuple[str, str], float] = defaultdict(float)
    sample_event: dict[str, Event] = {}
    first_of_request_month = request_date.replace(day=1)
    for event in ctx.events:
        if event.status != "settled" or event.direction != "debit":
            continue
        if event.category not in VARIABLE_CATEGORIES or event.amount is None:
            continue
        settle = event.settlement_date or event.event_date
        if settle is None or settle >= first_of_request_month:
            continue
        home = dataset.convert(
            event.amount, event.currency, ctx.profile.home_currency, settle.isoformat()
        )
        by_cat_month[(event.category, settle.strftime("%Y-%m"))] += home
        sample_event[event.category] = event

    months_by_cat: dict[str, list[float]] = defaultdict(list)
    for (category, month), total in sorted(by_cat_month.items()):
        months_by_cat[category].append(total)

    projected: list[CashFlow] = []
    dim = _days_in_month(request_date)
    remainder_end = _next_month(first_of_request_month) - timedelta(days=1)
    daily_cats = {"groceries", "transport"}
    for category, totals in months_by_cat.items():
        if category not in daily_cats:
            continue
        envelope = _variable_envelope(totals)
        if envelope <= 0 or dim <= 0:
            continue
        event = sample_event[category]
        daily = envelope / dim
        day = request_date + timedelta(days=1)
        while day <= remainder_end and day <= horizon:
            projected.append(
                _variable_flow(dataset, ctx, event, day, daily, "daily")
            )
            day += timedelta(days=1)

    cursor = _next_month(first_of_request_month)
    while cursor <= horizon:
        for category, totals in months_by_cat.items():
            envelope = _variable_envelope(totals)
            if envelope <= 0:
                continue
            event = sample_event[category]
            charge_day = date(cursor.year, cursor.month, min(28, max(1, request_date.day)))
            if charge_day > horizon:
                continue
            projected.append(
                _variable_flow(dataset, ctx, event, charge_day, envelope, "month")
            )
        cursor = _next_month(cursor)
    return projected


def _variable_flow(
    dataset: Dataset,
    ctx: RequestContext,
    event: Event,
    on_date: date,
    amount: float,
    kind: str,
) -> CashFlow:
    return CashFlow(
        on_date=on_date,
        amount=-amount,
        event_id=f"var:{event.category}:{kind}:{on_date.isoformat()}",
        series_key=f"variable|{event.category}",
        category=event.category,
        essential=event.category in ctx.profile.expense_categories_to_protect,
        source="projected",
        stoppable=_can_stop(ctx, event),
        reducible=_can_reduce(ctx, event),
        original_amount=amount,
        minimum_allowed_amount=_min_allowed_home(dataset, ctx, event, on_date),
        description=event.description,
    )
