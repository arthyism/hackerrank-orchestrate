"""90-day balance simulation and safe-to-pay search."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Optional

from models import CashFlow, RequestContext
from state_builder import FORECAST_DAYS


def simulate(
    ctx: RequestContext,
    *,
    extra_debits: Optional[list[tuple[date, float]]] = None,
    stopped_event_ids: Optional[set[str]] = None,
    reduced: Optional[dict[str, float]] = None,
) -> tuple[bool, float]:
    """Return (never_below_minimum, lowest_balance)."""
    stopped_event_ids = stopped_event_ids or set()
    reduced = reduced or {}
    extra_debits = extra_debits or []
    start = ctx.request.request_date
    end = start + timedelta(days=FORECAST_DAYS)
    by_day: dict[date, float] = {}

    for flow in ctx.cashflows:
        if flow.on_date < start or flow.on_date > end:
            continue
        if _is_stopped(flow, stopped_event_ids):
            continue
        amount = flow.amount
        base_id = flow.event_id.split(":proj:")[0]
        if base_id in reduced and amount < 0:
            amount = -min(abs(amount), reduced[base_id])
            if reduced[base_id] <= 0:
                continue
        by_day[flow.on_date] = by_day.get(flow.on_date, 0.0) + amount

    for pay_date, pay_amount in extra_debits:
        if start <= pay_date <= end:
            by_day[pay_date] = by_day.get(pay_date, 0.0) - pay_amount

    balance = ctx.profile.current_available_balance
    floor = ctx.profile.minimum_balance_to_keep
    lowest = balance
    if balance + 1e-9 < floor:
        return False, balance
    day = start
    while day <= end:
        if day in by_day:
            balance += by_day[day]
            lowest = min(lowest, balance)
            if balance + 1e-6 < floor:
                return False, lowest
        day += timedelta(days=1)
    return True, lowest


def amount_safe_today(ctx: RequestContext) -> float:
    requested = ctx.request.requested_amount
    if _safe_payment(ctx, [(ctx.request.request_date, requested)]):
        return _round_money(requested)
    lo, hi = 0.0, requested
    best = 0.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if _safe_payment(ctx, [(ctx.request.request_date, mid)]):
            best = mid
            lo = mid
        else:
            hi = mid
    return _round_money(best)


def earliest_full_payment(ctx: RequestContext) -> Optional[date]:
    requested = ctx.request.requested_amount
    start = ctx.request.request_date
    for offset in range(FORECAST_DAYS + 1):
        day = start + timedelta(days=offset)
        if _safe_payment(ctx, [(day, requested)]):
            return day
    return None


def _safe_payment(
    ctx: RequestContext,
    payments: Iterable[tuple[date, float]],
    stopped: Optional[set[str]] = None,
    reduced: Optional[dict[str, float]] = None,
) -> bool:
    ok, _ = simulate(ctx, extra_debits=list(payments), stopped_event_ids=stopped, reduced=reduced)
    return ok


def _is_stopped(flow: CashFlow, stopped_event_ids: set[str]) -> bool:
    if flow.event_id in stopped_event_ids:
        return True
    base = flow.event_id.split(":proj:")[0]
    return base in stopped_event_ids


def _round_money(value: float) -> float:
    return round(value + 1e-9, 2)
