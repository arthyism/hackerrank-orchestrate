"""Typed records for the Buy or Wait? dataset."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


def parse_date(value: str) -> Optional[date]:
    value = (value or "").strip()
    if not value:
        return None
    year, month, day = value.split("-")
    return date(int(year), int(month), int(day))


def parse_float(value: str) -> Optional[float]:
    value = (value or "").strip()
    if not value:
        return None
    return float(value)


def parse_pipe(value: str) -> list[str]:
    value = (value or "").strip()
    if not value:
        return []
    return [part for part in value.split("|") if part]


def parse_bool(value: str) -> bool:
    return (value or "").strip().lower() == "true"


@dataclass
class Profile:
    user_id: str
    home_currency: str
    current_available_balance: float
    minimum_balance_to_keep: float
    financial_priorities: list[str]
    expense_categories_to_protect: list[str]
    expense_categories_user_is_willing_to_reduce: list[str]
    expense_categories_user_is_willing_to_stop: list[str]
    payment_methods_user_will_consider: list[str]
    max_installment_months: Optional[int]


@dataclass
class Event:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str
    amount: Optional[float]
    currency: str
    event_date: Optional[date]
    settlement_date: Optional[date]
    status: str
    linked_event_id: str
    flexibility: str
    minimum_allowed_amount: Optional[float]


@dataclass
class Request:
    request_id: str
    user_id: str
    request_date: date
    request_type: str
    requested_amount: float
    desired_completion_date: date
    allows_partial_payment: bool
    request_text: str


@dataclass
class PaymentOption:
    payment_option_id: str
    request_id: str
    payment_method: str
    payment_amount: float
    number_of_payments: int
    first_payment_date: Optional[date]
    payment_frequency_days: Optional[int]
    financing_fee: float
    total_payable_amount: float


@dataclass
class Message:
    message_id: str
    user_id: str
    request_id: str
    related_event_id: str
    sent_at: str
    source_type: str
    message_text: str


@dataclass
class ImageLink:
    image_id: str
    user_id: str
    request_id: str
    related_event_id: str


@dataclass
class CashFlow:
    """Signed home-currency cash movement used by the 90-day simulator."""

    on_date: date
    amount: float  # credit +, debit -
    event_id: str
    series_key: str
    category: str
    essential: bool
    source: str  # explicit | projected
    stoppable: bool = False
    reducible: bool = False
    original_amount: float = 0.0
    minimum_allowed_amount: Optional[float] = None
    description: str = ""


@dataclass
class Plan:
    method: str
    payments: list[tuple[date, float]]
    spending_changes: list[str]
    total_paid: float
    option_id: str = ""
    status: str = ""
    explanation: str = ""

    @property
    def start_date(self) -> Optional[date]:
        return self.payments[0][0] if self.payments else None

    @property
    def last_date(self) -> Optional[date]:
        return self.payments[-1][0] if self.payments else None


@dataclass
class Decision:
    request_id: str
    amount_safe_to_pay: float
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: str
    spending_changes_needed: str
    decision_explanation: str


@dataclass
class RequestContext:
    request: Request
    profile: Profile
    events: list[Event]
    options: list[PaymentOption]
    messages: list[Message]
    images: list[ImageLink]
    cashflows: list[CashFlow] = field(default_factory=list)
    amount_overrides: dict[str, float] = field(default_factory=dict)
    evidence: Optional["EvidenceFacts"] = None


@dataclass
class EvidenceFacts:
    """Structured facts from messages/images. Never a payment decision."""

    salary_amount: Optional[float] = None
    salary_currency: Optional[str] = None
    salary_from_date: Optional[date] = None
    salary_payday: Optional[date] = None
    stop_future_salary: bool = False
    ignore_event_ids: list[str] = field(default_factory=list)
    notes: str = ""
