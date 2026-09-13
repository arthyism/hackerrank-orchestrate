# Sample Request Patterns

From `dataset/sample_requests.csv` (25 solved examples). Use for eval, not as labels for the 250 evaluation requests.

## By decision type

| Pattern | Example request_id | Key signals |
|---------|-------------------|-------------|
| Pay today (full) | request_01, request_09, request_16 | `affordable_now`, `full_payment`, plan = single payment on `request_date` |
| Installments | request_02, request_07, request_12, request_17, request_22 | `affordable_with_plan`, plan matches `request_payment_options.csv` exactly |
| Wait for payday | request_03, request_04, request_08, request_13, request_18, request_23 | `affordable_later`, `wait`, full amount on future `earliest_date_for_full_payment` |
| Partial payment | request_19 | `affordable_with_plan`, `partial_payment`, 2 payments summing to `requested_amount` |
| Stop subscription | request_06 | `stop:event_id` + `full_payment` today |
| Reduce expense | request_11 | `reduce_to:event_id:amount` + `full_payment` today |
| Stop + reduce | request_21 | Both `stop:` and `reduce_to:` on different events |
| Not affordable | request_05, request_10, request_15, request_20, request_25 | `not_affordable`, `not_recommended`, `payment_plan=none`, empty earliest date |
| Small safe but can't finish | request_14, request_24 | Some `amount_safe_to_pay` > 0 but full request not completable in 90 days → still `not_affordable` |

## Explanation style

Samples use short, factual explanations citing currency amounts and minimum balance, e.g.:

- *"Pay ZAR 25,256 today. This leaves at least ZAR 18,000 available over the next 90 days."*
- *"Do not make this payment by 12 January 2026. None of the available options keeps the ZAR 13,100 minimum protected."*
- *"Although EUR 597.74 is available today, the full amount cannot be completed safely within 90 days."*

## Eval workflow

Labeled samples are split **15 DEV / 10 HOLDOUT** (frozen in `code/evaluator.py`).

- Iterate only on DEV: `python3 code/main.py --eval-samples`
- Do not look at HOLDOUT until we are ready: `python3 code/main.py --eval-samples --eval-split holdout`
- Then run the 250 unlabeled `dataset/requests.csv`

DEV (15): `request_01, 02, 03, 05, 06, 07, 11, 14, 15, 18, 19, 20, 22, 23, 25`  
HOLDOUT (10): `request_04, 08, 09, 10, 12, 13, 16, 17, 21, 24`

The only labeled `partial_payment` (`request_19`) stays in DEV so we can learn that path. HOLDOUT still covers now / wait / installments / not_affordable / spending-changes.
