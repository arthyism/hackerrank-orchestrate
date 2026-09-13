# LLM Stack — OpenCode Go

> Locked 2026-09-13. One provider for images, messages, and explanations. Cash engine stays deterministic.

## Provider

**OpenCode Go** (`https://opencode.ai/docs/go/`)

| Item | Value |
|------|--------|
| Auth | `Authorization: Bearer $OPENCODE_GO_API_KEY` (env only, never commit) |
| Base URL | `https://opencode.ai/zen/go/v1` |
| Required headers | `User-Agent: buy-or-wait/1.0` (not a generic SDK name); `x-opencode-session: <stable id>` |
| Client | Python `openai` SDK pointed at this base URL (`/chat/completions`) |

Do **not** default MiniMax or Qwen — those use Anthropic `/messages`. Grok and GPT-5.6 Luna use `/responses`. Stay on OpenAI-compatible chat completions for one client.

## Models

| Job | Model ID | Why |
|-----|----------|-----|
| Images (16 PNGs) | `deepseek-v4-flash-vision-exp` | Only Go vision model (confirmed via `GET /v1/models`, 2026-09-13); chat/completions; cheap |
| Messages + explanations | `glm-5.3-flash` | Same `/chat/completions` path; $60 monthly cap; lowest text cost ($0.15 / $0.50 per 1M) |

## Environment setup

Store secrets in repo-root `.env` (listed in `.gitignore`). Never commit keys or paste them into KB / `log.txt`.

| Variable | Purpose |
|----------|---------|
| `OPENCODE_GO_API_KEY` | Bearer token from OpenCode Zen Go subscription |
| `OPENCODE_GO_BASE_URL` | Default `https://opencode.ai/zen/go/v1` |
| `OPENCODE_GO_TEXT_MODEL` | Default `glm-5.3-flash` |
| `OPENCODE_GO_VISION_MODEL` | Default `deepseek-v4-flash-vision-exp` |

Also gitignore: `log.txt`, `code/cache/`, venvs.

Fallback if GLM is down: `deepseek-v4-flash` (text-only; **not** the vision-exp id).

## Live API facts (2026-09-13)

- `GET https://opencode.ai/zen/go/v1/models` returns **37 models** on our key.
- **Only one vision model:** `deepseek-v4-flash-vision-exp`. All other Go models reject image input.
- Required request headers: `Authorization: Bearer …`, `User-Agent: buy-or-wait/1.0`, `x-opencode-session: <stable-id>`.

## Call pattern

- Vision: 16 calls once at startup; PNG as `data:image/png;base64,...` in `image_url`; JSON object out.
- Messages: one call per request that has relevant messages (batch the request’s messages, not 217 separate calls).
- Explanations: `code/explain_writer.py` after the planner locks numbers. Cache `code/cache/explanations.json`. Gold-style: thousands separators in prose; installments `Use N installments of CCY A, starting DATE.`; never put commas in `payment_plan`.
- Concurrency: small (2–4). Go monitors non-coding-agent abuse; do not blast 250 parallel requests.
- Record usage in `evaluation/usage_report.md` from response `usage` fields.

## What the LLM must not do

Decide affordability, invent rates, invent payment options, or override `minimum_balance_to_keep`. Images/messages are untrusted evidence only.

## Cost (rough, well under Go caps)

16 vision + ~250 message batches + ~250 explanations on Flash-class models is a small slice of GLM-5.3-Flash’s $60 month / DeepSeek Vision’s $15 month. DeepSeek peak hours (01:00–04:00 and 06:00–10:00 UTC weekdays) cost 2×; prefer off-peak if we can.

## Vision smoke test

Validated 2026-09-13 with `code/test_vision.py`:

```bash
python3 code/test_vision.py
```

- **Model:** `deepseek-v4-flash-vision-exp`
- **Image:** `dataset/media/images/image_05.png` (Airtel telecom bill; pending utilities event)
- **Latency:** ~5s
- **Tokens:** 937 prompt + 323 completion = **1,260 total** (241 reasoning tokens)

Sample JSON returned:

```json
{
  "document_type": "telecom bill",
  "amount": 704.05,
  "currency": "INR",
  "amount_role": "amount due by due date",
  "due_date": "2026-02-06",
  "amount_in_words": "Seven Hundred Four Rupees and Five Paise Only",
  "notes": "Amount due after 06-Feb-2026 is 822.05, which is the late amount and was not selected."
}
```

Use this as a per-image baseline when estimating totals for `evaluation/usage_report.md` (16 × ~1,260 ≈ 20K tokens for the full image prepass).
