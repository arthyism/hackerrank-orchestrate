# Current Status

> As of 2026-09-13 ~14:02 IST (~4h to deadline)

## DEV 15 (latest)

| Field | Hits |
|---|---|
| amount_safe_to_pay | 1/15 (7%) |
| affordability_status | 12/15 (80%) |
| recommended_payment_method | 13/15 (87%) |
| payment_plan | 13/15 (87%) |
| earliest_date_for_full_payment | 12/15 (80%) |
| spending_changes_needed | 13/15 (87%) |
| exact 6-field | 1/15 |

HOLDOUT has not been scored. No 250-row `output.csv` yet.

## LLM usage

- Text `glm-5.3-flash`: messages → `EvidenceFacts` (cached `code/cache/message_facts.json`, 13 sample keys so far)
- Vision `deepseek-v4-flash-vision-exp`: 16 PNGs → event amounts (13/16 cached)
- Code decides pay/wait. `--no-llm` skips both.

## Not done

- Spending-change search actually winning on request_06 / request_11
- Finish 3 remaining image JSON extracts
- HOLDOUT one-shot, then 250-row run + `evaluation/usage_report.md`
