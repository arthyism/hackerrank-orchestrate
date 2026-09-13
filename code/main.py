#!/usr/bin/env python3
"""Buy or Wait? — deterministic cash engine.

Two-phase run:
  1. Load every dataset CSV into memory once.
  2. For each request, slice that user's records and decide.

Usage:
  python3 code/main.py --eval-samples              # 15-row DEV split
  python3 code/main.py --eval-samples --eval-split holdout
  python3 code/main.py --request request_01
  python3 code/main.py --limit 50          # first 50 eval rows, resume-safe
  python3 code/main.py                     # remaining rows (skips ids already in output.csv)
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = Path(__file__).resolve().parent
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))

from data_loader import Dataset  # noqa: E402
from evaluator import (  # noqa: E402
    DEV_SAMPLE_IDS,
    HOLDOUT_SAMPLE_IDS,
    OUTPUT_FIELDS,
    score_row,
)
from image_reader import ensure_image_facts  # noqa: E402
from explain_writer import polish_explanation  # noqa: E402
from message_parser import parse_evidence  # noqa: E402
from models import Decision, Request  # noqa: E402
from planner import decide  # noqa: E402
from state_builder import build_cashflows  # noqa: E402
from validator import validate  # noqa: E402

OUTPUT_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]


def run_request(
    dataset: Dataset,
    request: Request,
    *,
    use_llm: bool = True,
    amount_overrides: dict[str, float] | None = None,
) -> Decision:
    ctx = dataset.for_request(request)
    ctx.amount_overrides = dict(amount_overrides or {})
    ctx.evidence = parse_evidence(ctx, use_llm=use_llm)
    facts = ctx.evidence
    if facts and (
        facts.salary_amount
        or facts.stop_future_salary
        or facts.ignore_event_ids
        or         facts.salary_payday
        or facts.next_salary_amount
        or facts.rent_increase_percent
        or facts.cancel_event_ids
    ):
        print(
            f"  {request.request_id} evidence: salary={facts.salary_amount} "
            f"{facts.salary_currency or ''} next={facts.next_salary_amount} "
            f"from={facts.salary_from_date} payday={facts.salary_payday} "
            f"stop={facts.stop_future_salary} rent+={facts.rent_increase_percent} "
            f"cancel={facts.cancel_event_ids} ignore={facts.ignore_event_ids}"
        )
    build_cashflows(dataset, ctx)
    decision = decide(ctx)
    decision = validate(ctx, decision)
    return polish_explanation(ctx, decision, use_llm=use_llm)


def write_csv(path: Path, rows: list[Decision]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(_row_dict(row))
    tmp.replace(path)


def _row_dict(row: Decision) -> dict[str, object]:
    return {
        "request_id": row.request_id,
        "amount_safe_to_pay": row.amount_safe_to_pay,
        "affordability_status": row.affordability_status,
        "recommended_payment_method": row.recommended_payment_method,
        "payment_plan": row.payment_plan,
        "earliest_date_for_full_payment": row.earliest_date_for_full_payment,
        "spending_changes_needed": row.spending_changes_needed,
        "decision_explanation": row.decision_explanation,
    }


def _decision_from_csv(row: dict[str, str]) -> Decision:
    return Decision(
        request_id=row["request_id"],
        amount_safe_to_pay=float(row["amount_safe_to_pay"]) if row["amount_safe_to_pay"] else 0.0,
        affordability_status=row["affordability_status"],
        recommended_payment_method=row["recommended_payment_method"],
        payment_plan=row["payment_plan"],
        earliest_date_for_full_payment=row["earliest_date_for_full_payment"],
        spending_changes_needed=row["spending_changes_needed"],
        decision_explanation=row.get("decision_explanation") or "",
    )


def load_output_rows(path: Path) -> dict[str, Decision]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["request_id"]: _decision_from_csv(row) for row in csv.DictReader(handle)}


def run_eval_dataset(
    dataset: Dataset,
    *,
    use_llm: bool,
    amount_overrides: dict[str, float] | None,
    out_path: Path,
    limit: int | None,
) -> int:
    done = load_output_rows(out_path)
    pending = [req for req in dataset.eval_requests if req.request_id not in done]
    if limit is not None:
        pending = pending[: max(0, limit)]
    print(
        f"Eval run llm={'on' if use_llm else 'off'}  "
        f"already={len(done)}  this_batch={len(pending)}  "
        f"total={len(dataset.eval_requests)}  out={out_path}",
        flush=True,
    )
    for request in pending:
        print(
            f"[{len(done)+1}/{len(dataset.eval_requests)}] {request.request_id}",
            flush=True,
        )
        decision = run_request(
            dataset, request, use_llm=use_llm, amount_overrides=amount_overrides
        )
        done[decision.request_id] = decision
        write_csv(out_path, _ordered_rows(dataset, done))
        print(
            f"  {decision.affordability_status}/{decision.recommended_payment_method} "
            f"safe={decision.amount_safe_to_pay} plan={decision.payment_plan}",
            flush=True,
        )
    print(f"Wrote {len(done)} rows to {out_path}", flush=True)
    return 0


def _ordered_rows(dataset: Dataset, done_map: dict[str, Decision]) -> list[Decision]:
    return [done_map[req.request_id] for req in dataset.eval_requests if req.request_id in done_map]


def eval_samples(
    dataset: Dataset,
    split: str,
    *,
    use_llm: bool = True,
    amount_overrides: dict[str, float] | None = None,
) -> int:
    allowed = {
        "dev": set(DEV_SAMPLE_IDS),
        "holdout": set(HOLDOUT_SAMPLE_IDS),
        "all": set(DEV_SAMPLE_IDS) | set(HOLDOUT_SAMPLE_IDS),
    }[split]
    requests = [req for req in dataset.sample_requests if req.request_id in allowed]
    print(f"Loaded {len(dataset.profiles)} profiles, {sum(len(v) for v in dataset.events_by_user.values())} events")
    print(f"Eval split={split}  n={len(requests)}  llm={'on' if use_llm else 'off'}")
    if split == "dev":
        print("Holdout locked: " + ", ".join(HOLDOUT_SAMPLE_IDS))
        print("Use --eval-split holdout only after we stop iterating on the 15.\n")
    elif split == "holdout":
        print("ONE-SHOT CHECK — do not retune on these 10 rows.\n")
    else:
        print("Full 25 (dev + holdout). Prefer --eval-split dev while iterating.\n")
    field_hits = {field: 0 for field in OUTPUT_FIELDS}
    exact = 0
    rows: list[Decision] = []
    for request in requests:
        decision = run_request(
            dataset, request, use_llm=use_llm, amount_overrides=amount_overrides
        )
        rows.append(decision)
        label = dataset.sample_labels[request.request_id]
        hits = score_row(decision, label)
        all_ok = all(hits.values())
        exact += int(all_ok)
        for field, ok in hits.items():
            field_hits[field] += int(ok)
        mark = "OK" if all_ok else "MISS"
        print(
            f"{request.request_id:12} {mark:4}  "
            f"pred={decision.affordability_status}/{decision.recommended_payment_method}  "
            f"gold={label['affordability_status']}/{label['recommended_payment_method']}  "
            f"safe={decision.amount_safe_to_pay} gold_safe={label['amount_safe_to_pay']}"
        )
        if not all_ok:
            bad = [name for name, ok in hits.items() if not ok]
            print(f"             mismatch: {', '.join(bad)}")
            print(f"             pred plan={decision.payment_plan}")
            print(f"             gold plan={label['payment_plan']}")
            print(f"             pred earliest={decision.earliest_date_for_full_payment!r} gold={label['earliest_date_for_full_payment']!r}")
            print(f"             pred changes={decision.spending_changes_needed} gold={label['spending_changes_needed']}")
    n = len(requests)
    print("\nField accuracy:")
    for field in OUTPUT_FIELDS:
        print(f"  {field:32} {field_hits[field]}/{n} ({100 * field_hits[field] / n:.0f}%)")
    print(f"  exact 6-field match              {exact}/{n} ({100 * exact / n:.0f}%)")
    out_name = {"dev": "sample_dev_output.csv", "holdout": "sample_holdout_output.csv", "all": "sample_output.csv"}[split]
    write_csv(ROOT / "code" / "cache" / out_name, rows)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Buy or Wait? financial agent")
    parser.add_argument(
        "--eval-samples",
        action="store_true",
        help="Score labeled samples (default split: 15-row DEV)",
    )
    parser.add_argument(
        "--eval-split",
        choices=("dev", "holdout", "all"),
        default="dev",
        help="dev=15 iterate set (default), holdout=10 locked, all=25",
    )
    parser.add_argument("--no-llm", action="store_true", help="Skip message + vision LLM; rules only")
    parser.add_argument(
        "--refresh-images",
        action="store_true",
        help="Delete image_facts.json and re-extract all 16 PNGs",
    )
    parser.add_argument("--request", help="Run a single request_id")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N unfinished eval requests (resume-safe)",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "output.csv"),
        help="Output CSV path (default: repo-root output.csv)",
    )
    args = parser.parse_args()

    cache_dir = ROOT / "code" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    if args.refresh_images:
        cache_file = cache_dir / "image_facts.json"
        if cache_file.exists():
            cache_file.unlink()
            print("Cleared image_facts.json")
    dataset = Dataset.load()

    use_llm = not args.no_llm
    print("Loading image amounts (one-shot cache)...")
    amount_overrides = ensure_image_facts(dataset, use_llm=use_llm)

    if args.eval_samples:
        return eval_samples(dataset, args.eval_split, use_llm=use_llm, amount_overrides=amount_overrides)

    if args.request:
        request = dataset.request_by_id(args.request)
        decision = run_request(dataset, request, use_llm=use_llm, amount_overrides=amount_overrides)
        print(",".join(OUTPUT_COLUMNS))
        print(
            ",".join(
                str(getattr(decision, col) if col != "request_id" else decision.request_id)
                for col in OUTPUT_COLUMNS
            )
        )
        return 0

    return run_eval_dataset(
        dataset,
        use_llm=use_llm,
        amount_overrides=amount_overrides,
        out_path=Path(args.out),
        limit=args.limit,
    )


if __name__ == "__main__":
    sys.exit(main())
