# Project Summary — Buy or Wait?

HackerRank Orchestrate (September 2026) — **Buy or Wait?**

Build an AI-powered financial agent that, for every purchase/payment request in `dataset/requests.csv`, decides whether the user should pay in full, pay partially, use installments, wait, or not proceed.

## Deadline

**September 13, 2026, 6:00 PM IST**

## Submission URL

https://www.hackerrank.com/contests/hackerrank-orchestrate-september26/challenges/buy-or-wait/submission

## Submission bundle (3 files)

| File | Description |
|------|-------------|
| `code.zip` | Runnable solution + `evaluation/usage_report.md` (token/cost report). Exclude `dataset/`, venvs, node_modules |
| `output.csv` | 250 predictions at repo root (one row per `request_id` in `dataset/requests.csv`) |
| `log.txt` | Chat transcript from repo root (gitignored, upload at submit time) |

## Repo

- Starter: `https://github.com/interviewstreet/hackerrank-orchestrate-september26`
- Entry point: `python3 code/main.py`
- Spec: `problem_statement.md`, agent rules: `AGENTS.md`

## Post-submission

- **AI Judge interview** opens immediately after first submission (30 min, camera mandatory)
- Interview window: 12 hours after first submit
- Final results: September 15, 2026

## Scoring dimensions

Hidden test cases judge: `amount_safe_to_pay`, `affordability_status`, `recommended_payment_method`, `payment_plan`, `earliest_date_for_full_payment`, `spending_changes_needed`, `decision_explanation`.
