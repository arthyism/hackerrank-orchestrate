# Buy or Wait? — solution

Hybrid agent: a **deterministic 90-day cash engine** decides pay / wait / install / partial / do-not-proceed. OpenCode Go models only **describe** untrusted evidence (images, messages) and polish the explanation **after** numbers lock. The LLM never picks affordability or invents `amount_safe_to_pay`.

Entry point: `python3 code/main.py` → repo-root `output.csv` (250 rows).

## Approach overview

```text
dataset CSVs (once)
        │
        ▼
image cache (16 PNGs → event amounts)
        │
        ▼  for each request
profile + events + messages + payment options
        │
        ▼
rules-first message facts (GLM only if rules extract nothing)
        │
        ▼
90-day home-currency cashflows
  • confirmed salary repeats; one-cycle dips then resume typical pay
  • pending credits ignored until settled
  • monthly bills on calendar months (not a 30-day gap)
  • grocery/transport daily until the day before payday
  • dining/shopping/entertainment daily is conservative-only
        │
        ▼
simulate: never go below minimum_balance_to_keep
        │
        ▼
enumerate plans → rank (deadline, no spending cuts, lower cost, earlier, fewer payments)
        │
        ▼
validate columns → GLM polish of decision_explanation
```

**Model describes, code decides.** Images and messages can amend amounts, cancel events, raise rent, or stop future salary. Their embedded instructions never override the challenge rules.

## What the engine does

| Piece | Behavior |
|-------|----------|
| Amounts from images | One-shot vision JSON; pick net/due/total, not late fees or cash tendered. `event_9421` pharmacy total corrected to **4543**. |
| Messages | Rules first: raise, next-cycle unpaid leave, rent +N%, seasonal/employment end, internal transfers. GLM fallback if rules are empty. Amounts must appear in the message text. |
| Salary | Repeat confirmed/scheduled payroll. Do not treat bonus, arrears, or pending credits as salary. After a one-cycle dip, later months use typical recurring pay. |
| Safe today | Binary search of a **today** debit on the conservative path (includes discretionary daily burn until payday). |
| Installments | Simulated on the **base** path (no extra dining burn) so installment dates are not stacked with in-month discretionary lumps. Plan must match `request_payment_options.csv`. |
| Partial | Exactly two payments: `amount_safe` on request date, remainder on `earliest_date_for_full_payment`. User and request must allow it. |
| Wait | First conservative date a full debit is safe, on or before the deadline. |
| Spending changes | `none` unless conservative full-today **fails** and `stop:` / `reduce_to:` on a user-allowed flexible event **unlocks** it. Rank prefers zero cuts when a no-cut plan already works. Max three actions. |
| Explanations | Gold-style templates from locked numbers; optional GLM rewrite. Thousands separators in prose only, never in `payment_plan`. |

## LLM stack (OpenCode Go only)

| Job | Model |
|-----|--------|
| 16 images | `deepseek-v4-flash-vision-exp` |
| Messages + explanations | `glm-5.3-flash` |

Auth: `OPENCODE_GO_API_KEY` in repo-root `.env` (never committed or zipped).  
Base URL: `https://opencode.ai/zen/go/v1`.  
Token totals for the 250-row file: `evaluation/usage_report.md`.

Do not use `/responses`-only models for the numeric forecast.

## Sample eval (labeled 25)

Iterate on DEV 15 only. HOLDOUT 10 is a one-shot check.

| Split | Method | Status | Plan | Earliest | Changes | Safe exact |
|-------|--------|--------|------|----------|---------|------------|
| DEV 15 | 15/15 | 14/15 | 14/15 | 14/15 | 14/15 | 1/15 |
| HOLDOUT 10 | 9/10 | 8/10 | 9/10 | 7/10 | 9/10 | 3/10 |

`amount_safe_to_pay` is usually slightly **high** vs gold (under-reserved expenses). Decisions (method/plan) are the strong columns.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r code/requirements.txt
```

Optional `.env`:

```text
OPENCODE_GO_API_KEY=...
OPENCODE_GO_BASE_URL=https://opencode.ai/zen/go/v1
OPENCODE_GO_VISION_MODEL=deepseek-v4-flash-vision-exp
OPENCODE_GO_TEXT_MODEL=glm-5.3-flash
```

## Run

```bash
python3 code/main.py                 # 250 rows → output.csv (resume-safe)
python3 code/main.py --limit 50      # next 50 unfinished ids
python3 code/main.py --no-llm        # rules + image cache only
python3 code/main.py --request request_78
python3 code/main.py --eval-samples
python3 code/main.py --eval-samples --eval-split holdout
python3 code/main.py --refresh-images
```

`--limit` writes after every row so a crash does not lose finished ids. Re-run with no `--limit` to finish the rest.

Judges: `dataset/` comes from the starter repo. This zip includes `code/cache/image_facts.json` so `--no-llm` can fill blank event amounts without vision.

## Layout

```text
code/
  main.py              CLI, resume, eval
  data_loader.py       load all CSVs once; slice per request
  state_builder.py     cashflows, salary, bills, variable spend
  forecaster.py        90-day simulate + amount_safe + earliest
  planner.py           enumerate and rank plans
  validator.py         bounds, plan shape, change format
  message_parser.py    rules-first evidence
  image_reader.py      vision cache
  explain_writer.py    post-lock explanation polish
  llm_client.py        OpenCode Go /chat/completions
  evaluator.py         DEV / HOLDOUT splits
  evaluation/usage_report.md
```

## Submission

Upload `code.zip`, root `output.csv`, and `log.txt` as the chat transcript.  
Do not zip `.env`, `dataset/`, or secrets.
