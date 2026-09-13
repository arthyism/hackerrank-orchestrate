"""Load every dataset CSV once, then slice by request_id / user_id."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

from models import (
    Event,
    ImageLink,
    Message,
    PaymentOption,
    Profile,
    Request,
    RequestContext,
    parse_bool,
    parse_date,
    parse_float,
    parse_pipe,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET = REPO_ROOT / "dataset"


class Dataset:
    """In-memory index of all participant CSVs.

    Phase 1: ``Dataset.load()`` reads every file once.
    Phase 2: ``for_request(request_id)`` returns only that user's slice.
    """

    def __init__(self) -> None:
        self.profiles: dict[str, Profile] = {}
        self.events_by_user: dict[str, list[Event]] = defaultdict(list)
        self.events_by_id: dict[str, Event] = {}
        self.options_by_request: dict[str, list[PaymentOption]] = defaultdict(list)
        self.messages_by_user: dict[str, list[Message]] = defaultdict(list)
        self.messages_by_request: dict[str, list[Message]] = defaultdict(list)
        self.images_by_request: dict[str, list[ImageLink]] = defaultdict(list)
        self.images_by_event: dict[str, ImageLink] = {}
        self.fx: dict[tuple[str, str, str], float] = {}
        self.fx_by_pair: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
        self.sample_requests: list[Request] = []
        self.eval_requests: list[Request] = []
        self.sample_labels: dict[str, dict[str, str]] = {}

    @classmethod
    def load(cls, dataset_dir: Optional[Path] = None) -> "Dataset":
        data = cls()
        root = dataset_dir or DATASET
        data._load_profiles(root / "financial_profiles.csv")
        data._load_events(root / "financial_events.csv")
        data._load_options(root / "request_payment_options.csv")
        data._load_messages(root / "messages.csv")
        data._load_images(root / "images.csv")
        data._load_fx(root / "exchange_rates.csv")
        data.sample_requests, data.sample_labels = data._load_requests(
            root / "sample_requests.csv", labeled=True
        )
        data.eval_requests, _ = data._load_requests(root / "requests.csv", labeled=False)
        return data

    def for_request(self, request: Request) -> RequestContext:
        user_id = request.user_id
        extra_messages = [
            m
            for m in self.messages_by_user.get(user_id, [])
            if not m.request_id or m.request_id == request.request_id
        ]
        by_id = {m.message_id: m for m in extra_messages}
        for m in self.messages_by_request.get(request.request_id, []):
            by_id[m.message_id] = m
        return RequestContext(
            request=request,
            profile=self.profiles[user_id],
            events=list(self.events_by_user.get(user_id, [])),
            options=list(self.options_by_request.get(request.request_id, [])),
            messages=list(by_id.values()),
            images=list(self.images_by_request.get(request.request_id, [])),
        )

    def request_by_id(self, request_id: str) -> Request:
        for req in self.sample_requests + self.eval_requests:
            if req.request_id == request_id:
                return req
        raise KeyError(request_id)

    def convert(self, amount: float, from_ccy: str, to_ccy: str, on_date: str) -> float:
        if from_ccy == to_ccy:
            return amount
        key = (on_date, from_ccy, to_ccy)
        if key in self.fx:
            return amount * self.fx[key]
        reverse = (on_date, to_ccy, from_ccy)
        if reverse in self.fx and self.fx[reverse]:
            return amount / self.fx[reverse]
        pair = (from_ccy, to_ccy)
        rows = self.fx_by_pair.get(pair, [])
        prior = [rate for day, rate in rows if day <= on_date]
        if prior:
            return amount * prior[-1]
        rev_pair = (to_ccy, from_ccy)
        rev_rows = self.fx_by_pair.get(rev_pair, [])
        prior_rev = [rate for day, rate in rev_rows if day <= on_date]
        if prior_rev and prior_rev[-1]:
            return amount / prior_rev[-1]
        raise KeyError(f"No FX {from_ccy}->{to_ccy} on {on_date}")

    def _load_profiles(self, path: Path) -> None:
        for row in _read(path):
            max_months = parse_float(row["max_installment_months"])
            self.profiles[row["user_id"]] = Profile(
                user_id=row["user_id"],
                home_currency=row["home_currency"],
                current_available_balance=float(row["current_available_balance"]),
                minimum_balance_to_keep=float(row["minimum_balance_to_keep"]),
                financial_priorities=parse_pipe(row["financial_priorities"]),
                expense_categories_to_protect=parse_pipe(row["expense_categories_to_protect"]),
                expense_categories_user_is_willing_to_reduce=parse_pipe(
                    row["expense_categories_user_is_willing_to_reduce"]
                ),
                expense_categories_user_is_willing_to_stop=parse_pipe(
                    row["expense_categories_user_is_willing_to_stop"]
                ),
                payment_methods_user_will_consider=parse_pipe(
                    row["payment_methods_user_will_consider"]
                ),
                max_installment_months=int(max_months) if max_months is not None else None,
            )

    def _load_events(self, path: Path) -> None:
        for row in _read(path):
            event = Event(
                event_id=row["event_id"],
                user_id=row["user_id"],
                event_type=row["event_type"],
                description=row["description"],
                category=row["category"],
                direction=row["direction"],
                amount=parse_float(row["amount"]),
                currency=row["currency"],
                event_date=parse_date(row["event_date"]),
                settlement_date=parse_date(row["settlement_date"]),
                status=row["status"],
                linked_event_id=row["linked_event_id"].strip(),
                flexibility=row["flexibility"],
                minimum_allowed_amount=parse_float(row["minimum_allowed_amount"]),
            )
            self.events_by_id[event.event_id] = event
            self.events_by_user[event.user_id].append(event)

    def _load_options(self, path: Path) -> None:
        for row in _read(path):
            option = PaymentOption(
                payment_option_id=row["payment_option_id"],
                request_id=row["request_id"],
                payment_method=row["payment_method"],
                payment_amount=float(row["payment_amount"]),
                number_of_payments=int(row["number_of_payments"] or 0),
                first_payment_date=parse_date(row["first_payment_date"]),
                payment_frequency_days=(
                    int(row["payment_frequency_days"])
                    if row["payment_frequency_days"].strip()
                    else None
                ),
                financing_fee=float(row["financing_fee"] or 0),
                total_payable_amount=float(row["total_payable_amount"]),
            )
            self.options_by_request[option.request_id].append(option)

    def _load_messages(self, path: Path) -> None:
        for row in _read(path):
            msg = Message(
                message_id=row["message_id"],
                user_id=row["user_id"],
                request_id=row["request_id"].strip(),
                related_event_id=row["related_event_id"].strip(),
                sent_at=row["sent_at"],
                source_type=row["source_type"],
                message_text=row["message_text"],
            )
            self.messages_by_user[msg.user_id].append(msg)
            if msg.request_id:
                self.messages_by_request[msg.request_id].append(msg)

    def _load_images(self, path: Path) -> None:
        for row in _read(path):
            link = ImageLink(
                image_id=row["image_id"],
                user_id=row["user_id"],
                request_id=row["request_id"].strip(),
                related_event_id=row["related_event_id"].strip(),
            )
            if link.request_id:
                self.images_by_request[link.request_id].append(link)
            if link.related_event_id:
                self.images_by_event[link.related_event_id] = link

    def _load_fx(self, path: Path) -> None:
        for row in _read(path):
            pair_day = (row["rate_date"], row["from_currency"], row["to_currency"])
            rate = float(row["rate"])
            self.fx[pair_day] = rate
            self.fx_by_pair[(row["from_currency"], row["to_currency"])].append(
                (row["rate_date"], rate)
            )
        for pair in self.fx_by_pair:
            self.fx_by_pair[pair].sort()

    def _load_requests(
        self, path: Path, labeled: bool
    ) -> tuple[list[Request], dict[str, dict[str, str]]]:
        requests: list[Request] = []
        labels: dict[str, dict[str, str]] = {}
        for row in _read(path):
            req = Request(
                request_id=row["request_id"],
                user_id=row["user_id"],
                request_date=parse_date(row["request_date"]),
                request_type=row["request_type"],
                requested_amount=float(row["requested_amount"]),
                desired_completion_date=parse_date(row["desired_completion_date"]),
                allows_partial_payment=parse_bool(row["allows_partial_payment"]),
                request_text=row["request_text"],
            )
            requests.append(req)
            if labeled:
                labels[req.request_id] = {
                    "amount_safe_to_pay": row["amount_safe_to_pay"],
                    "affordability_status": row["affordability_status"],
                    "recommended_payment_method": row["recommended_payment_method"],
                    "payment_plan": row["payment_plan"],
                    "earliest_date_for_full_payment": row["earliest_date_for_full_payment"],
                    "spending_changes_needed": row["spending_changes_needed"],
                    "decision_explanation": row["decision_explanation"],
                }
        return requests, labels


def _read(path: Path) -> Iterable[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)
