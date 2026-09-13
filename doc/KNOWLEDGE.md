# Workspace Knowledge Base

> Last updated: 2026-09-13 (~15:51 IST)
> `/recall` — load context in a new chat. `/ingest` — save curated session summary.

## Project Summary

HackerRank Orchestrate (September 2026) — **Buy or Wait?** Build an AI financial agent that decides pay-in-full, partial, installments, wait, or do-not-proceed for each row in `dataset/requests.csv`. Deadline **Sept 13, 2026 6:00 PM IST**. Submit `code.zip`, root `output.csv`, and `log.txt`. Details: [`doc/chunks/project-summary.md`](chunks/project-summary.md).

## Current Status

- Deterministic pipeline + grounded message LLM + **image cache 16/16**
- **DEV 15 (after calendar-month bills + conservative lump-sum + salary-resume):** amount_safe **1/15**, status **14/15 (93%)**, method **15/15 (100%)**, plan **14/15**, earliest **14/15**, changes **14/15**, exact **1/15** (`request_01`)
- HOLDOUT 10 after the same engine fixes (measurement, not a retune target): exact **3/10**, method/plan **9/10 (90%)**, status **8/10**, amount_safe **3/10**. New exact: `request_12`. `request_04` now wait-correct.
- Forecast: grocery/transport daily until payday; dining/shopping/entertainment daily is **conservative_only** (amount_safe + today lump-sum, not installments). Monthly bills use **calendar months**, not a 30-day gap. After a one-cycle pay dip, later salary resumes the typical amount. Spending-change full-pay uses the base path so `stop:` can unlock a plan.
- GLM `explain_writer.py` after lock; gold-style templates; commas in prose only. Last dump: `code/cache/sample_dev_output.csv`
- **Submit bundle ready:** root `output.csv` (250), `code.zip` (includes `evaluation/usage_report.md`), `log.txt` as chat_transcript. No `.env` in the zip.
- Unlabeled 50-row audit (5 ids): spec-valid; `--no-llm` matches locked numbers. One prose WARN (`request_46` says “installments” for a legal partial). No engine retune.
- Do **not** use `gpt-5.6-luna` for the 90-day numeric forecast

Full scores + gaps: [`doc/chunks/eval-results.md`](chunks/eval-results.md). Status: [`doc/chunks/current-status.md`](chunks/current-status.md).

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
- **Image cache wired:** `code/image_reader.py` → `code/cache/image_facts.json` keyed by `event_id`; `ensure_image_facts()` once at startup; per-request `amount_overrides` lookup only (warm load ~360ms)
- DeepSeek vision may return JSON in `reasoning_content` — parser reads both fields; use `max_tokens=2500`
- **`image_14` / `event_9421`:** verified pharmacy TOTAL **4543** (vision misread 4593; corrected in cache + `VERIFIED_AMOUNT_CORRECTIONS`)
- **Salary forecast**: repeat confirmed/scheduled payroll monthly; never after `Final employer payroll`; never treat arrears/bonus as salary
- Message layer is **rules-first** (`rules_from_messages`): raise, remaining salary, unpaid-leave next pay, rent +N%, seasonal/employment end, internal transfers. GLM only if rules extract nothing. Cache `code/cache/evidence_v2.json` by `user_id`
- `EvidenceFacts` now includes `next_salary_amount`, `rent_increase_percent`, `cancel_event_ids`, `event_amount_overrides`, `skip_internal_transfers`. Applied in `state_builder` before projection
- Expense repeat tag is internal and rule-based: bills with monthly cadence; variable cats need 2+ months; groceries/transport burn **daily until the day before payday** (not through calendar month-end). LLM does not classify series
- **DEV 15 after `daily_until_payday`:** method/plan **14/15**, amount_safe still **1/15**. Evidence v2 schema helps 250-row message types more than these 15
- HOLDOUT 10 one-shot (2026-09-13): exact 2/10 (`request_09`, `request_16`); method 7/10; amount_safe 2/10; `request_21` gold needs stop+reduce; `request_12` LLM `stop_future_salary` may have killed installments
- Pred `amount_safe_to_pay` is usually **too high**. Do not put dining lumps on installment dates. `request_02` raise IDR 42750000 from 2025-08-15 is required for gold installments
- LLM e2e 2026-09-13: reviewer OK on locked numbers; `_fmt_explain_amount` in prose; `_fmt_amount` (no commas) in `payment_plan`
- **Muse Spark 1.3 experiment rejected** (2026-09-13): `--muse` + `llm_advisor.py` in isolate worktree `iterate/forecast-safe` only — **not merged to `main`**. Full Muse override of scored fields dropped DEV status to 9/15; amount_safe-only Muse did not beat baseline. Muse 1.3 often HTTP 500. See [`muse-experiment.md`](chunks/muse-experiment.md).
- **Shipped forecast path on `main`:** `CashFlow.conservative_only` discretionary burn + `simulate(conservative=True)` for lump-sum/partial/wait/`amount_safe`; installments use normal sim. This beat Muse on decision fields (DEV method 15/15, holdout exact 3/10).

Deep dives: [`dataset-map`](chunks/dataset-map.md) · [`output-schema-rules`](chunks/output-schema-rules.md) · [`sample-patterns`](chunks/sample-patterns.md) · [`resubmission-policy`](chunks/resubmission-policy.md) · [`muse-experiment`](chunks/muse-experiment.md)

## Open Questions

- How far to search for `earliest_date_for_full_payment` if not safe within 90 days?
- Confirm resubmission behavior on HackerRank submission page

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
| Eval results | `doc/chunks/eval-results.md` | DEV/HOLDOUT scores, ablations, known gaps, caches |
| Image extraction | `doc/chunks/image-extraction.md` | 16 docs, field-selection traps, VLM JSON prepass |
| LLM stack | `doc/chunks/llm-stack.md` | OpenCode Go provider, vision vs text models |
| Muse experiment (not shipped) | `doc/chunks/muse-experiment.md` | Muse 1.3 worktree attempt; rejected vs conservative_only |
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
| 2026-09-13 | `image_reader.py` wired; 16/16 in `image_facts.json`; per-request lookup only; `--refresh-images` |
| 2026-09-13 | Corrected `event_9421` pharmacy TOTAL to 4543 (vision had 4593) |
| 2026-09-13 | HOLDOUT 10 one-shot: exact 2/10, method/plan 70%, amount_safe 2/10 — do not retune on these rows |
| 2026-09-13 | Rules-first evidence v2: next-salary, rent %, cancel, transfers; LLM fallback only; DEV method/plan unchanged 87% |
| 2026-09-13 | Case study: amount_safe leaks are in-month variable + planner fallback; Luna not for forecast; GLM explanations after lock |
| 2026-09-13 | Ablations on DEV 15: daily grocery/transport only until payday wins (method/plan 14/15). Prepay/var_max lose installments. Shipped daily_until_payday |
| 2026-09-13 | Ingest handoff: DEV 15 field table, HOLDOUT lock, LLM e2e = no-llm on scores, explanation templates, eval-results chunk |
| 2026-09-13 | Fixed skipped request-month bills (calendar step), conservative discretionary for lump-sum only, resume typical salary after a dip. DEV method 15/15; holdout exact 3/10 method 9/10 |
| 2026-09-13 | Spec audit of request_26/29/30/31/46 in 50-row output: 4 PASS, 1 explanation WARN; ship remaining 200 |
| 2026-09-13 | Ingest: Muse 1.3 experiment doc (worktree only, not merged); conservative_only on main is shipped forecast path |
