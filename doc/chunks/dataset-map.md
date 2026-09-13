# Dataset Map

All participant files live in `dataset/`. Only `requests.csv` needs predictions.

## Files

| File | Rows / size | Purpose |
|------|-------------|---------|
| `requests.csv` | 250 | Evaluation requests — predict these |
| `sample_requests.csv` | 25 | Solved examples for dev/eval only |
| `financial_profiles.csv` | ~276 users | Balance, min balance, priorities, protected categories, payment prefs |
| `financial_events.csv` | ~25K | Historical, pending, settled, cancelled, unrealized transactions |
| `request_payment_options.csv` | 2–4 options/request | Full payment and installment schedules |
| `exchange_rates.csv` | Fixed dated rates | INR, ZAR, IDR, USD, EUR conversions |
| `messages.csv` | ~217 | Payroll updates, cancellations, amendments (untrusted evidence) |
| `images.csv` | 16 links | PNGs at `dataset/media/images/<image_id>.png` |
| `output.csv` | Blank template | Reference only; write predictions to **repo root** `output.csv` |

## Join keys

- `user_id` — profiles, events, messages
- `request_id` — requests, payment options, messages, images
- `event_id` / `related_event_id` — events ↔ messages/images
- Exchange rates — match on rate date + currency pair direction

## Currencies

INR, ZAR, IDR, USD, EUR — all amounts in user's `home_currency` from profile.

## Special handling

- Blank `amount` on an event → find linked image via `images.csv`, extract amount (VLM/OCR). **Never treat blank as zero.**
- `linked_event_id` — same transaction lifecycle; resolve conflicts per problem rules
- Pending debits: reserve; pending credits: ignore until settled
- Unrealized investments: not available cash

## Request types

`purchase`, `travel`, `education`, `family_transfer`, `debt_repayment`, `investment`, `housing`, `emergency_expense`, `other`
