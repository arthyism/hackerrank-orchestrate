"""Score agent output against sample_requests.csv labels."""

from __future__ import annotations

from models import Decision

# Frozen 15/10 split of the 25 labeled samples.
# Iterate only on DEV. Do not tune against HOLDOUT until we are ready
# for a one-shot check. Split is stratified by decision type so neither
# set is only "easy" or only "hard" rows.
DEV_SAMPLE_IDS = (
    "request_01",  # affordable_now / full_payment
    "request_02",  # installments
    "request_03",  # wait
    "request_05",  # not_affordable
    "request_06",  # stop + full_payment
    "request_07",  # installments
    "request_11",  # reduce_to + full_payment
    "request_14",  # not_affordable (cash today, cannot finish)
    "request_15",  # not_affordable
    "request_18",  # wait
    "request_19",  # partial_payment (only labeled partial — keep in DEV)
    "request_20",  # not_affordable
    "request_22",  # installments
    "request_23",  # wait
    "request_25",  # not_affordable
)

HOLDOUT_SAMPLE_IDS = (
    "request_04",  # wait
    "request_08",  # wait
    "request_09",  # affordable_now
    "request_10",  # not_affordable
    "request_12",  # installments
    "request_13",  # wait
    "request_16",  # affordable_now
    "request_17",  # installments
    "request_21",  # stop + reduce
    "request_24",  # not_affordable (cash today, cannot finish)
)

assert len(DEV_SAMPLE_IDS) == 15
assert len(HOLDOUT_SAMPLE_IDS) == 10
assert len(set(DEV_SAMPLE_IDS) & set(HOLDOUT_SAMPLE_IDS)) == 0
assert set(DEV_SAMPLE_IDS) | set(HOLDOUT_SAMPLE_IDS) == {
    f"request_{i:02d}" for i in range(1, 26)
}

OUTPUT_FIELDS = [
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
]


def score_row(decision: Decision, label: dict[str, str]) -> dict[str, bool]:
    pred = {
        "amount_safe_to_pay": _num(decision.amount_safe_to_pay),
        "affordability_status": decision.affordability_status,
        "recommended_payment_method": decision.recommended_payment_method,
        "payment_plan": decision.payment_plan,
        "earliest_date_for_full_payment": decision.earliest_date_for_full_payment,
        "spending_changes_needed": decision.spending_changes_needed,
    }
    gold = {
        "amount_safe_to_pay": _num(label["amount_safe_to_pay"]) if label["amount_safe_to_pay"] else None,
        "affordability_status": label["affordability_status"],
        "recommended_payment_method": label["recommended_payment_method"],
        "payment_plan": label["payment_plan"],
        "earliest_date_for_full_payment": label["earliest_date_for_full_payment"],
        "spending_changes_needed": label["spending_changes_needed"],
    }
    hits = {}
    for field in OUTPUT_FIELDS:
        if field == "amount_safe_to_pay":
            hits[field] = _close(pred[field], gold[field])
        else:
            hits[field] = pred[field] == gold[field]
    return hits


def _num(value) -> float | None:
    if value is None or value == "":
        return None
    return round(float(value), 2)


def _close(left, right) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    scale = max(1.0, abs(right))
    return abs(left - right) <= max(0.05, 0.002 * scale)
