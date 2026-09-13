# Workspace Knowledge Base

> Last updated: 2026-09-13
> `/recall` — load context in a new chat. `/ingest` — save curated session summary.

## Project Summary

HackerRank Orchestrate (September 2026) — **Buy or Wait?** Build an AI financial agent that decides pay-in-full, partial, installments, wait, or do-not-proceed for each row in `dataset/requests.csv`. Deadline **Sept 13, 2026 6:00 PM IST**. Submit `code.zip`, root `output.csv`, and `log.txt`. Details: [`doc/chunks/project-summary.md`](chunks/project-summary.md).

## Current Status

- Deterministic pipeline + grounded message LLM + image amount cache (partial)
- Repeat vs one-off for expenses is **deterministic** (cadence / 2+ months). Do not add an output.csv column; do not LLM-tag every series
- Current-month grocery/transport daily burn added; lumping all remaining spend on request_date broke installments
- DEV 15: method/plan **87%**, `amount_safe_to_pay` still **1/15 exact** but several near-misses (`request_02` 18.7M vs 17.2M; `request_22` 495 vs 475)

Full status: [`doc/chunks/current-status.md`](chunks/current-status.md).

## Key Decisions

- **Hybrid architecture**: deterministic 90-day forecaster + LLM/VLM for messages/images/explanations
- **Data load is two-phase**: load all CSVs once; run the engine per `request_id` (not one-user-only, not 250 isolated file reads)
- **Provider**: OpenCode Go only (`OPENCODE_GO_API_KEY`, `https://opencode.ai/zen/go/v1`)
- **Models**: `deepseek-v4-flash-vision-exp` (16 images); `glm-5.3-flash` (messages + explanations)
- **Eval-first**: iterate on 15 DEV samples; 10 HOLDOUT stay locked until a one-shot check; then full 250
- **Submit baseline early** to unlock AI Judge interview, then improve if resubmit allowed

## Architecture & Approach

Suggested modules: `data_loader`, `state_builder`, `forecaster`, `planner`, `validator`, `evaluator`, optional `message_parser` + `image_reader`. Entry: `python3 code/main.py` → root `output.csv`.

Full plan: [`doc/chunks/architecture-plan.md`](chunks/architecture-plan.md).

## Important Findings

- 250 eval requests; 25 solved samples; 16 images; 5 currencies (INR, ZAR, IDR, USD, EUR)
- Installment plans must exactly match `request_payment_options.csv`
- Partial payment = exactly 2 payments summing to `requested_amount`
- Spending changes only on flexible recurring events (`stop:` / `reduce_to:`)
- Blank event amounts → linked image, never treat as zero
- All 16 blank amounts map 1:1 to 16 PNGs; pick **net/due/total**, not line items, cash tendered, or late fees
- Forecast-critical images: salary net pay (01), outstanding rent (02), pending telecom (05), pending grocery invoice (10), scheduled hospital (11)
- OpenCode Go vision validated end-to-end: `deepseek-v4-flash-vision-exp` on `image_05` returned correct due amount (704.05 INR), rejected late fee (822.05)
- **Salary forecast**: repeat confirmed/scheduled payroll monthly; never after `Final employer payroll`; never treat arrears/bonus as salary
- Message LLM (`code/message_parser.py`) extracts salary/bonus facts; code decides. Ignore-ids never drop bills. `request_02` raise is required for the gold installment path
- Expense repeat tag is internal and rule-based: bills with monthly cadence; variable cats need 2+ months; groceries/transport burn daily through month-end. LLM does not classify series
- DEV 15: method/plan 87%; amount_safe still 1/15 exact

Deep dives: [`dataset-map`](chunks/dataset-map.md) · [`output-schema-rules`](chunks/output-schema-rules.md) · [`sample-patterns`](chunks/sample-patterns.md) · [`resubmission-policy`](chunks/resubmission-policy.md)

## Open Questions

- How far to search for `earliest_date_for_full_payment` if not safe within 90 days?
- Confirm resubmission behavior on HackerRank submission page
- Confirm `OPENCODE_GO_API_KEY` is set in the local environment before the full run — **done** (`.env`, gitignored)

## Topics Index

| Topic | Location | Summary |
|-------|----------|---------|
| Project overview | `doc/chunks/project-summary.md` | Deadline, submission URL, 3-file bundle |
| Current status | `doc/chunks/current-status.md` | Done / not done / next steps |
| Dataset map | `doc/chunks/dataset-map.md` | CSV files, join keys, special handling |
| Output rules | `doc/chunks/output-schema-rules.md` | 8 columns, 90-day safety, plan ranking |
| Sample patterns | `doc/chunks/sample-patterns.md` | 25 example decision types |
| Resubmission | `doc/chunks/resubmission-policy.md` | Likely multi-submit before deadline |
| Architecture | `doc/chunks/architecture-plan.md` | Module layout and pipeline |
| Image extraction | `doc/chunks/image-extraction.md` | 16 docs, field-selection traps, VLM JSON prepass |
| LLM stack | `doc/chunks/llm-stack.md` | OpenCode Go provider, vision vs text models |
| KB usage | `doc/README.md` | `/setup`, `/recall`, `/ingest` |

## Changelog

| Date | Change |
|------|--------|
| 2026-09-12 | Renamed commands to /setup, /recall; kept /ingest |
| 2026-09-12 | Ingested full hackathon context: 7 chunks + updated master KB |
| 2026-09-12 | Image extraction plan: 16 PNGs, field-selection rules, one-shot VLM cache |
| 2026-09-13 | Locked LLM stack: OpenCode Go; vision=`deepseek-v4-flash-vision-exp`; text=`glm-5.3-flash` |
| 2026-09-13 | Vision smoke test OK on image_05 via `code/test_vision.py` (704.05 INR, due 2026-02-06) |
| 2026-09-13 | Salary projector: monthly confirmed pay; skip final payroll and arrears; request_01 exact match on DEV |
| 2026-09-13 | Message LLM wired; facts grounded in message text; DEV method/plan 93%; amount_safe still 7% |
| 2026-09-13 | Variable spend: skip 1-month one-offs; daily grocery/transport remainder. No LLM series tag |
