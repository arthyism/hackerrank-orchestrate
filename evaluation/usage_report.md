# Token usage — final 250-row `output.csv`

Run: `python3 code/main.py` in 50-row resume batches (2026-09-13).  
Provider: **OpenCode Go** (`https://opencode.ai/zen/go/v1`).  
Cash engine is deterministic. LLMs do not choose pay/wait or invent `amount_safe_to_pay`.

## Models

| Job | Provider | Model | This run |
|-----|----------|-------|----------|
| Images (16 PNGs, cached) | OpenCode Go | `deepseek-v4-flash-vision-exp` | Cache hit 16/16. Prior extract logged below. |
| Messages (rules-first; GLM if rules empty) | OpenCode Go | `glm-5.3-flash` | 84 calls on eval `request_26`–`request_275` |
| Explanations (after numbers lock) | OpenCode Go | `glm-5.3-flash` | 250 calls (one per eval row) |

## Final-run GLM (`request_26`–`request_275`)

| Stage | Calls | Input tokens | Output tokens | Total |
|-------|------:|-------------:|--------------:|------:|
| Messages | 84 | 43,682 | 17,022 | 60,704 |
| Explanations | 250 | 74,064 | 11,785 | 85,849 |
| **GLM eval total** | **334** | **117,746** | **28,807** | **146,553** |

Average GLM tokens per eval request (250 rows, including rows with no message call): **586**.  
Average among the 84 message calls: **723**.  
Average explanation call: **343**.

## Image prepass (used by this `output.csv`)

Logged during cache build (includes smoke/retries):

| Model | Calls | Input | Output | Total |
|-------|------:|------:|-------:|------:|
| `deepseek-v4-flash-vision-exp` | 63 | 49,098 | 47,903 | 97,001 |

Effective unique images in `code/cache/image_facts.json`: **16**.

## Estimated cost (list rates; no keys)

| Model | Input $/1M | Output $/1M | Estimated USD |
|-------|-----------:|------------:|--------------:|
| `glm-5.3-flash` (eval 334 calls) | 0.15 | 0.50 | **0.032** |
| `glm-5.3-flash` (all logged GLM, incl. DEV) | 0.15 | 0.50 | 0.039 |
| `deepseek-v4-flash-vision-exp` (all logged vision) | Flash-class | | small vs Go monthly caps |

**Estimated cost of the 250-row prediction file (GLM eval + 16-image cache):** about **$0.04–0.10**.  
**Per-request average (250):** about **0.6k tokens**, **~$0.0002**.

## Notes

- `request_179` message GLM returned no JSON; rules-only evidence was used; row still written.
- One spending-change row in the 250 (`affordable_with_plan` + `full_payment`).
- No API keys or credentials in this file.
