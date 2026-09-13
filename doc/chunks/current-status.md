# Current Status

> As of 2026-09-13 ~15:20 IST (~2.5h to deadline 18:00 IST)

## Latest scores (after engine fixes, `--no-llm`)

**DEV 15:** amount_safe 1/15 · status **14/15** · method **15/15** · plan **14/15** · earliest **14/15** · changes **14/15** · exact 1/15

**HOLDOUT 10:** exact **3/10** (`request_09`, `12`, `16`) · method/plan **9/10** · status **8/10** · amount_safe **3/10** · earliest **7/10**

## What we just fixed

- Monthly bills stepped with `_add_months`, not median 30-day gap (that skipped rent on the due weekday)
- Dining/shopping/entertainment daily burn is `conservative_only` — used for `amount_safe` and today full-pay, not installments
- After unpaid-leave / one-cycle `next_salary`, later months use typical recurring pay (not the dipped last slip)
- If employment ended, skip discretionary monthly envelopes
- Spending-change full-pay simulates on the base path so `stop:` can unlock (DEV `request_06` now `stop:event_476`)

## Not done

- Upload the three files (bundle is built). Interview unlocks on first submit.
- `request_08` wait still fails the 90-day sim (safe 304 vs gold 285; method still not_recommended)
- `request_11` / `request_21` still skip gold reduce/stop (conservative full-today still passes)
- `request_19` method is now partial; first-pay 32767 vs gold 28820
