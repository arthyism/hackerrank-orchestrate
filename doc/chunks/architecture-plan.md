# Architecture Plan

Suggested hybrid approach: **deterministic financial core** + **LLM/VLM for unstructured evidence**.

## Module layout

```text
code/
├── main.py              # CLI: python3 code/main.py → writes root output.csv
├── data_loader.py       # Load & join all CSVs
├── state_builder.py     # Reconstruct user finances, resolve conflicts, detect recurrence
├── message_parser.py    # LLM/rules for payroll amendments, cancellations
├── image_reader.py      # One-shot VLM JSON for 16 PNGs; fill blank event amounts
├── forecaster.py        # 90-day balance simulation
├── planner.py           # Generate & rank payment plans
├── explain_writer.py    # GLM polish of decision_explanation after numbers lock
├── validator.py         # Deterministic output checks (bounds, plan match, flexible-only changes)
├── evaluator.py         # Score against sample_requests.csv
├── run_ablations.py     # DEV-only forecast variants (use_llm=False)
└── evaluation/
    └── usage_report.md  # Required for submission — token/cost summary
```

## Pipeline per request

**Startup (once):**

1. `Dataset.load()` — read all CSVs into memory
2. `ensure_image_facts(dataset)` — 16 vision calls max; write/read `code/cache/image_facts.json`
3. Build global `amount_overrides: dict[event_id, float]`

**Per request (250×):**

1. `dataset.for_request(request_id)` — slice user profile, events, messages, options
2. Attach `amount_overrides` (lookup only; no vision)
3. `parse_evidence` — messages (separate per-request cache in `message_facts.json`)
4. `build_cashflows` — blank event amounts filled from overrides
5. `decide` + `validate` → output row
6. `polish_explanation` — GLM rewrite; cache `code/cache/explanations.json`. Must not change scored numeric fields.

## Design choices (open)

- **Rules-first vs LLM-first**: samples suggest deterministic forecasting is critical; LLM best for messages/images/explanations
- **LLM provider locked**: OpenCode Go — vision `deepseek-v4-flash-vision-exp`, text `glm-5.3-flash` (see `llm-stack.md`)
- **Forecast horizon**: 90 days per spec; `earliest_date_for_full_payment` may need search beyond 90 days if never safe
- **Determinism**: keep core logic deterministic where possible for reproducibility

## Run commands

```bash
python3 code/main.py                    # full dataset → output.csv
python3 code/main.py --eval-samples     # DEV 15 vs sample gold
python3 code/main.py --eval-samples --eval-split holdout
python3 code/main.py --refresh-images   # re-run 16-image vision extract
python3 code/main.py --no-llm           # skip GLM/vision; rules + image cache still apply
python3 code/run_ablations.py           # DEV forecast variants
```
