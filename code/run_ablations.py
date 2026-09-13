#!/usr/bin/env python3
"""Score DEV 15 under several forecast flags. Does not touch holdout."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE))

from data_loader import Dataset
from evaluator import DEV_SAMPLE_IDS, OUTPUT_FIELDS, score_row
from exp_flags import reset
from image_reader import ensure_image_facts
from main import run_request

CONFIGS = [
    ("base", {}),
    ("var_max", {"var_max": True}),
    ("prepay", {"prepay": True}),
    ("prepay_50", {"prepay": True, "prepay_scale": 0.5}),
    ("prepay_25", {"prepay": True, "prepay_scale": 0.25}),
    ("daily_payday", {"daily_until_payday": True}),
    ("lump_daily_pd", {"lump_daily_to_payday": True, "daily_until_payday": True}),
    ("max+prepay50", {"var_max": True, "prepay": True, "prepay_scale": 0.5}),
    ("max+lump_pd", {"var_max": True, "lump_daily_to_payday": True, "daily_until_payday": True}),
]


def score_dev(dataset, overrides) -> dict:
    hits = {field: 0 for field in OUTPUT_FIELDS}
    exact = 0
    method_ok = []
    safe_ok = []
    n = 0
    for req in dataset.sample_requests:
        if req.request_id not in DEV_SAMPLE_IDS:
            continue
        n += 1
        decision = run_request(dataset, req, use_llm=False, amount_overrides=overrides)
        label = dataset.sample_labels[req.request_id]
        row = score_row(decision, label)
        exact += int(all(row.values()))
        for field, ok in row.items():
            hits[field] += int(ok)
        if row["recommended_payment_method"]:
            method_ok.append(req.request_id)
        if row["amount_safe_to_pay"]:
            safe_ok.append(req.request_id)
    return {"n": n, "exact": exact, "hits": hits, "method_ok": method_ok, "safe_ok": safe_ok}


def main() -> int:
    dataset = Dataset.load()
    overrides = ensure_image_facts(dataset, use_llm=False)
    print(f"{'config':16} exact  safe  status  method  plan  earliest  changes")
    best = None
    for name, flags in CONFIGS:
        reset(**flags)
        result = score_dev(dataset, overrides)
        n = result["n"]
        h = result["hits"]
        line = (
            f"{name:16} {result['exact']:2}/{n}   "
            f"{h['amount_safe_to_pay']:2}/{n}  "
            f"{h['affordability_status']:2}/{n}    "
            f"{h['recommended_payment_method']:2}/{n}    "
            f"{h['payment_plan']:2}/{n}  "
            f"{h['earliest_date_for_full_payment']:2}/{n}       "
            f"{h['spending_changes_needed']:2}/{n}"
        )
        print(line)
        score = (
            result["exact"],
            h["recommended_payment_method"] + h["payment_plan"],
            h["amount_safe_to_pay"],
            h["affordability_status"],
        )
        if best is None or score > best[0]:
            best = (score, name, result)
    reset()
    print("\nBest by (exact, method+plan, safe, status):", best[1] if best else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
