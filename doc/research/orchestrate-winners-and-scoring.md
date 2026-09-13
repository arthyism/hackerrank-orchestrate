# Orchestrate Winners & AI Scoring Research

> ⚠️ **NOT FOR SUBMISSION** — Internal research only. Do **not** include this file in `code.zip` or upload as part of `log.txt`. Delete or exclude before packaging if accidentally copied.

> Researched: 2026-09-12 via subagent + HackerRank blogs, winner posts, public repos.

---

## Important note on "last year"

Orchestrate **launched May 2026** — there is no prior year. Past editions: **May, June, August 2026**. This doc covers all three.

---

## Winners by edition

### May 2026 — Support Triage (HackerRank / Claude / Visa)

| Rank | Name | Standing point |
|------|------|----------------|
| #1 | **Saai Syvendra** (Sri Lanka) | One agent, one tool; hybrid BM25+dense+rerank; pre-LLM injection guard; citation guard |
| #2 | **Bhavya Khatri** (India) | Strong architecture + AI Judge defense |
| #3 | **Faraaz Khan** (Argentina) | 6-stage pipeline, ~400 lines Node, deterministic gate before LLM |

Scale: 12,885 registered · 1,349 completed interview.

### June 2026 — Multimodal Damage Claims

| Rank | Name | Standing point |
|------|------|----------------|
| #1 | **Sristee Shrivastava** | #122→#1; "model describes, code decides"; mock interview was decisive |
| #2 | **Hitakshi Arora** | #15 in May → #2; same pattern |
| #3 | **Swayam Mishra** | #60→#3; post-model Python safety gate |

### August 2026 — WhatsApp Message Router

| Rank | Name | Standing point |
|------|------|----------------|
| #1 | **Mrinal Desai** | #174 in June → #1; personalization; 5-level deterministic policy cascade |
| #2 | **Caleb Andersen** | 70→5→2 arc; interview prep was the fix |
| #3 | **Muhammad Rifqi Haikal** (Indonesia) | Top 3 of ~1,983 interviewed |

---

## Why winners won — common patterns

1. **"Model describes, code decides"** — LLM for context/reasoning; deterministic code for final decision
2. **Deterministic safety gates** — escalate/abstain when uncertain; never hallucinate
3. **Structured output + schema validation** — retry on invalid output
4. **Eval loop on sample data** — build → run → fix failures → regression test
5. **Grounded explanations** — cite evidence; generic justifications score poorly (~70 cap even if action correct)
6. **Mock AI Judge interview** — top 3 often within ~0.5 pts on code; interview decided rank (Sristee)
7. **Balanced across all 4 metrics** — every Top 10 was top-quartile on **all four** signals

### Architecture stats (May cohort, n=1,349)

| Architecture | Best rank | Top 10 count |
|--------------|-----------|--------------|
| Single agent + tools/RAG | 1 | 7 |
| Graph / state-machine | 2 | 1 |
| Multi-stage pipeline | 3 | 2 |
| Single mega-prompt | 77 | 0 |

---

## Official scoring formula

```
Final = 0.10 × Chat Transcript
      + 0.30 × AI Judge Interview
      + 0.30 × Output CSV
      + 0.30 × Code ZIP
```

Each signal: 0–100. Same LLM judge method across cohort.

**Tie-break order:** Interview → Code → Output → Chat

### What each signal measures

| Signal | Weight | Key checks |
|--------|--------|------------|
| **Output CSV** | 30% | Per-row column accuracy; whole-submission safety; explanation quality |
| **Code ZIP** | 30% | Architecture 30%, prompts/tools 30%, robustness 25%, engineering 15% — **observable code only** |
| **AI Judge Interview** | 30% | Technical depth 40%, judgment 25%, clarity 20%, honesty 15% |
| **Chat Transcript** | 10% | Ownership 35%, specificity 25%, iteration 25%, safety awareness 15% |

### Critical insight

Sorting by **Output CSV alone** captures only **12 of actual Top 50**. No single metric reproduces the leaderboard.

Interview has **weakest correlation** with code/output (ρ ~0.28) — strong builders can still lose rank here without prep.

---

## Time allocation recommendation (24h)

1. Ship working output on full dataset (250 rows)
2. Build defensible architecture you can trace in code
3. **Mock AI Judge** (1–2 hours) — highest ROI
4. Maintain honest chat log (plan → test → fix → pushback)
5. Submit early for interview window

---

## September 2026 "Buy or Wait?" — apply learnings

- **Deterministic cash engine** is the product; LLM for messages/images/explanations only
- Validate installment plans match `request_payment_options.csv` exactly in code
- Ground `decision_explanation` in specific events/dates/amounts
- Test on 25 samples before full 250 run
- Prepare interview: 90-day forecast, pending debits, wait vs not_recommended, spending changes

---

## Sources

- https://www.hackerrank.com/blog/behind-the-scenes-of-hackerrank-orchestrate/
- https://www.hackerrank.com/blog/getting-better-at-orchestrate/
- https://github.com/interviewstreet/hackerrank-orchestrate-may26/blob/main/evalutation_criteria.md
- Saai: https://github.com/saai-syvendra/hackerrank-orchestrate
- Sristee: https://medium.com/@sristee45/how-i-went-from-122-to-1-in-24-hours-building-a-multimodal-damage-claim-verifier-for-hackerrank-92cdc18242b2
- May winners: https://www.linkedin.com/posts/hackerrank_we-just-wrapped-hackerrank-orchestrate-a-activity-7460947208390176769-VT4w
- August winners: https://www.linkedin.com/posts/hackerrank_the-august-edition-of-orchestrate-brought-activity-7491471696382558208-2ebA
