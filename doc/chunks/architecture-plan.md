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
├── validator.py         # Deterministic output checks (bounds, plan match, flexible-only changes)
├── evaluator.py         # Score against sample_requests.csv
└── evaluation/
    └── usage_report.md  # Required for submission — token/cost summary
```

## Pipeline per request

1. Load user profile + events up to `request_date`
2. Apply messages/images to amend/cancel/confirm facts
3. Build recurring schedule + one-time future cash flows
4. Compute `amount_safe_to_pay` and `earliest_date_for_full_payment`
5. Enumerate eligible plans: full, partial, each installment option, wait, spending-change variants
6. Filter by 90-day safety + user preferences + `max_installment_months`
7. Rank surviving plans per tie-break rules
8. Generate `decision_explanation`
9. Validate output schema before writing row

## Design choices (open)

- **Rules-first vs LLM-first**: samples suggest deterministic forecasting is critical; LLM best for messages/images/explanations
- **LLM provider locked**: OpenCode Go — vision `deepseek-v4-flash-vision-exp`, text `glm-5.3-flash` (see `llm-stack.md`)
- **Forecast horizon**: 90 days per spec; `earliest_date_for_full_payment` may need search beyond 90 days if never safe
- **Determinism**: keep core logic deterministic where possible for reproducibility

## Run commands

```bash
python3 code/main.py                    # full dataset → output.csv
python3 code/main.py --eval-samples     # optional: score against sample_requests.csv
```
