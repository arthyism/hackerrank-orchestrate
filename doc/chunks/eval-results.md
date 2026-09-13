# Eval Results And Handoff Notes

> Last updated 2026-09-13 ~15:00 IST. Iterate on **DEV 15 only**. Do **not** retune on HOLDOUT.

## Official splits

| Split | IDs |
|-------|-----|
| DEV 15 | `request_01,02,03,05,06,07,11,14,15,18,19,20,22,23,25` |
| HOLDOUT 10 (locked) | `request_04,08,09,10,12,13,16,17,21,24` |

Commands:

```bash
python3 code/main.py --eval-samples                    # DEV 15
python3 code/main.py --eval-samples --eval-split holdout  # one-shot only
python3 code/main.py --no-llm --eval-samples           # rules + caches, no GLM/vision
python3 code/main.py                                   # 250-row root output.csv (not produced yet)
```

`--no-llm` still runs **rules-first** message extract. It does not call GLM/vision. Image amounts still come from `code/cache/image_facts.json`.

## DEV 15 — latest (daily_until_payday + LLM on)

Scored fields **identical** with `--no-llm` and `--llm`. GLM does not change pay/wait or `amount_safe_to_pay`.

| Field | Hits |
|-------|------|
| amount_safe_to_pay | **1/15 (7%)** — only `request_01` exact |
| affordability_status | 13/15 (87%) |
| recommended_payment_method | **14/15 (93%)** |
| payment_plan | **14/15 (93%)** |
| earliest_date_for_full_payment | 12/15 (80%) |
| spending_changes_needed | 13/15 (87%) |
| exact 6-field | **1/15** (`request_01`) |

Rows written to `code/cache/sample_dev_output.csv` after the LLM e2e pass.

Older notes saying method/plan **87%** are **pre-`daily_until_payday`**. Ignore those as current.

## HOLDOUT 10 — one-shot (do not retune)

| Field | Hits |
|-------|------|
| amount_safe_to_pay | 2/10 (20%) |
| affordability_status | 6/10 (60%) |
| recommended_payment_method | 7/10 (70%) |
| payment_plan | 7/10 (70%) |
| earliest_date_for_full_payment | 5/10 (50%) |
| spending_changes_needed | 9/10 (90%) |
| exact 6-field | 2/10 (`request_09`, `request_16`) |

`request_21` gold wants stop+reduce. `request_12` may have been hurt by LLM `stop_future_salary`. Do not chase HOLDOUT IDs.

## Ablations (DEV 15, `use_llm=False`)

Script: `python3 code/run_ablations.py`

| Variant | Result | Shipped? |
|---------|--------|----------|
| `daily_until_payday` | method/plan **14/15**; grocery/transport daily burn stops the day before payday | **Yes** |
| Pre-payday dining/shopping reserve | `request_02` safe 18.7M → 17.72M (gold 17.2M) but **broke installments** | No — reverted |
| `var_max` | amount_safe 2/15 but method 11/15 | No |

Same 90-day cash path drives both `amount_safe_to_pay` and installment feasibility. Tightening reserves often kills the gold installment path.

## Known DEV gaps (do not overfit IDs)

| Request | Symptom |
|---------|---------|
| `request_02` | Needs raise IDR **42750000** from 2025-08-15 for gold 3-installment path. Rules should already extract this. |
| `request_19` | Isolated today-pay looks “safe” (~39660); gold partial first pay 28820 + 10840 on the 15th. Partial skipped because `safe == requested`. |
| `request_06` | Gold `stop:event_476`. Full pay still simulates; rank prefers **zero** spending changes. |
| `request_11` | Gold `reduce_to:event_989:665950`. Variable flow ids are `{event_id}:proj:…` so the name exists; rank still prefers no changes. |
| `request_20` | Pred ~21k vs gold ~5.4k |
| `request_03` | Pred ~1.23M vs gold ~873k |
| `request_25` | Pred ~4.0M vs gold ~1.4M |
| `request_22` | Close: 495 vs 475 |
| `request_15` | Close: 104 vs 83 |

Typical leak: pred safe **too high** (under-reserved expenses). Trough is often the **day before payday**.

Spending-change plans are **always enumerated**; ranking still prefers zero changes. Next lever if iterating: plan-aware `amount_safe` / ranking so 06/11/19 move — **without** putting dining lumps on installment dates.

## LLM e2e + reviewer (2026-09-13)

Pipeline: image cache → rules + GLM messages → forecast → decide → validate → `polish_explanation`.

Reviewer: no invented amounts; `payment_plan` must **not** use thousands commas (`_fmt_amount`). Prose uses `_fmt_explain_amount` (commas) only.

Gold-style templates:

- Installments: `Use N installments of CCY A, starting DATE.`
- Wait: `Pay CCY A in full on DATE. Paying earlier would take the balance below the CCY MIN minimum.`
- Full: `Pay CCY A today. This leaves at least CCY MIN available over the next 90 days.`

`request_01` explanation matches gold style after review. Cache: `code/cache/explanations.json` (delete if templates change).

**Do not** use `gpt-5.6-luna` for the 90-day numeric forecast (Go `/responses` only; non-deterministic). Amount safe is a ledger sim.

## Caches

| File | Role |
|------|------|
| `code/cache/image_facts.json` | 16/16 vision; `event_9421` pharmacy TOTAL **4543** (vision had 4593) |
| `code/cache/evidence_v2.json` | GLM message fallback, keyed by `user_id` |
| `code/cache/explanations.json` | Post-lock GLM prose |
| `code/cache/sample_dev_output.csv` | Last DEV 15 e2e dump |

Message cache is empty for unseen eval user ids. Full 250 will trigger ~200 GLM message calls then cache.

## Not produced yet

- Root `output.csv` for 250 requests
- `evaluation/usage_report.md` (required in `code.zip`)
