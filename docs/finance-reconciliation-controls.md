# Finance reconciliation controls

The 16 reconciliation controls that `mart_reconciliation_exceptions`
implements. This document is Finance-facing — it describes *what each
control means and what Finance should do*, not the SQL.

## Exception model

- **Grain**: one row per reconciliation exception. `exception_id` =
  `exception_code : entity_type : entity_id`.
- **`entity_type`**: `INVOICE`, `CAPTURE`, `FINANCIAL_EVENT`, or
  `SETTLEMENT` — the object to investigate.
- **`exception_amount_eur`**: a **non-negative magnitude** ("how much
  money is affected"), never a signed accounting amount. `NULL` when a
  meaningful EUR magnitude cannot be computed (e.g. no reference FX).
- **`business_date`**, **`product_id` / `product_name`**, **`currency`**,
  **`control_source`** locate the exception; `observed_amount_eur` /
  `expected_amount_eur` / `difference_amount_eur` describe it where the
  control has both sides.
- One source problem can produce more than one exception row when it
  legitimately trips more than one control.

## Status model

| Status | Meaning |
| --- | --- |
| `RECONCILED` | controls pass — not written as an exception row |
| `PENDING` | the condition holds but is still inside its allowed window |
| `OPEN_BREAK` | a confirmed break that needs investigation |
| `RESOLVED` | the condition occurred but has already been closed (e.g. a late settlement that has since arrived) |
| `EXCLUDED` | deliberately removed from the active queue |

## Severity model

| Severity | Meaning |
| --- | --- |
| `INFO` | visible, no action yet |
| `WARNING` | review, lower business impact |
| `CRITICAL` | investigate now |

**Status and severity are different dimensions**: status is a lifecycle
state, severity is urgency / business impact.

## Aging policy

Two controls are time-based. Inside the window they are informational;
past it they are breaks.

| Control | Window | Inside window | Past window |
| --- | --- | --- | --- |
| `MISSING_SETTLEMENT` | 5 calendar days from the event | `PENDING` / `INFO` | `OPEN_BREAK` / `CRITICAL` |
| `MISSING_BANK_RECEIPT` | 2 calendar days from a PAID settlement | `PENDING` / `INFO` | `OPEN_BREAK` / `CRITICAL` |

`age_days` on the exception row is the age used for this decision.

---

## Payment lifecycle

### `MISSING_CAPTURE`
- **Meaning**: Billing treats an invoice as collected, but PSP has no
  successful capture for it.
- **Compares**: Billing invoice status ↔ PSP financial events.
- **Trigger**: invoice is `PAID` (or otherwise collected) with zero
  `CAPTURE` events.
- **Policy**: `OPEN_BREAK` / `CRITICAL`.
- **Finance action**: confirm whether cash was actually taken; correct
  Billing or chase the PSP.

### `CAPTURE_AMOUNT_MISMATCH`
- **Meaning**: the amount PSP captured differs from the invoice total.
- **Compares**: Billing invoice total ↔ PSP capture amount (same
  currency).
- **Trigger**: currencies agree but `capture_amount ≠ invoice_total`
  beyond the €0.01 tolerance.
- **Policy**: `OPEN_BREAK` / `CRITICAL`.
- **Finance action**: identify the correct amount; adjust the invoice or
  raise a partial refund / additional charge.

### `DUPLICATE_CAPTURE`
- **Meaning**: one invoice has more than one successful capture — the
  customer was likely charged twice.
- **Compares**: PSP captures grouped by Billing invoice.
- **Trigger**: `capture_count > 1` for an invoice.
- **Policy**: `OPEN_BREAK` / `CRITICAL`.
- **Finance action**: refund the duplicate; check for a systemic retry
  bug.

### `INVALID_REFUND`
- **Meaning**: a refund points at a capture that does not exist.
- **Compares**: PSP `REFUND` event ↔ the `CAPTURE` it references.
- **Trigger**: `original_capture_id` does not resolve to a real capture.
- **Policy**: `OPEN_BREAK` / `CRITICAL`.
- **Finance action**: find the true parent capture or reverse the
  refund; the money left the business without an anchor.

### `OVER_REFUND`
- **Meaning**: cumulative refunds against a capture exceed the captured
  amount.
- **Compares**: sum of `REFUND` amounts ↔ the original `CAPTURE` amount.
- **Trigger**: `Σ refunds > capture` beyond tolerance.
- **Policy**: `OPEN_BREAK` / `CRITICAL`.
- **Finance action**: recover the over-refunded amount; review refund
  authorization limits.

---

## Settlement

### `MISSING_SETTLEMENT`
- **Meaning**: a captured (or refunded / charged-back) event never
  appeared in a PSP payout.
- **Compares**: PSP financial event ↔ PSP settlement items.
- **Trigger**: no settlement item for the event. Aging policy applies
  (5-day window).
- **Policy**: `PENDING` / `INFO` ≤ 5 days; `OPEN_BREAK` / `CRITICAL`
  after.
- **Finance action**: inside the window, wait; past it, query the PSP
  for the missing payout.

### `LATE_SETTLEMENT`
- **Meaning**: the event was settled, but later than the expected
  window.
- **Compares**: capture date ↔ matched settlement date.
- **Trigger**: settlement delay exceeds the expected range; the
  settlement *has* arrived.
- **Policy**: `RESOLVED` / `WARNING` — the cash is in, this is a
  timeliness signal.
- **Finance action**: none per row; watch the trend for a PSP SLA
  problem.

### `SETTLEMENT_TOTAL_MISMATCH`
- **Meaning**: the settlement header total does not equal the sum of its
  items.
- **Compares**: `settlements` header amounts ↔ `Σ settlement_items`.
- **Trigger**: header gross / fee / net differs from the item roll-up
  beyond tolerance.
- **Policy**: `OPEN_BREAK` / `CRITICAL`.
- **Finance action**: reconcile the payout line by line with the PSP;
  bank and accounting downstream follow the header and will be wrong.

---

## Bank

### `MISSING_BANK_RECEIPT`
- **Meaning**: a PAID PSP settlement has no matching bank credit.
- **Compares**: PSP settlement `bank_reference` ↔ bank
  `payment_reference`.
- **Trigger**: no bank transaction for the settlement. Aging policy
  applies (2-day window).
- **Policy**: `PENDING` / `INFO` ≤ 2 days; `OPEN_BREAK` / `CRITICAL`
  after.
- **Finance action**: past the window, treat as cash not received —
  escalate to the PSP and bank.

### `BANK_AMOUNT_MISMATCH`
- **Meaning**: the bank credited a different amount than the settlement
  net payout.
- **Compares**: settlement `net_payout` ↔ bank `amount`.
- **Trigger**: amounts differ beyond the €0.01 tolerance (reference is
  matched).
- **Policy**: `OPEN_BREAK` / `CRITICAL`.
- **Finance action**: identify the shortfall / overpayment; open a case
  with the PSP.

---

## Accounting

### `MISSING_LEDGER_POSTING`
- **Meaning**: a business object that must be posted has no POSTED
  journal entry.
- **Compares**: financial event / settlement ↔ `journal_lines`
  referencing it.
- **Trigger**: `posted_journal_entry_count = 0`.
- **Policy**: `OPEN_BREAK` / `CRITICAL`.
- **Finance action**: post the missing entry; the GL is understated.

### `LEDGER_AMOUNT_MISMATCH`
- **Meaning**: the posted journal amount differs from the expected
  management-EUR value of the object.
- **Compares**: posted expected-account debit / credit ↔
  `event_amount_eur`.
- **Trigger**: exactly one posted entry, and a leg is off by more than
  €0.01.
- **Policy**: `OPEN_BREAK` / `CRITICAL`.
- **Finance action**: correct the journal amount.

### `UNBALANCED_JOURNAL`
- **Meaning**: a posted journal entry's debits and credits do not equal.
- **Compares**: `Σ debit` ↔ `Σ credit` within the entry.
- **Trigger**: balance difference beyond €0.01. Takes precedence over
  `LEDGER_AMOUNT_MISMATCH` for the same entry.
- **Policy**: `OPEN_BREAK` / `CRITICAL`.
- **Finance action**: fix the entry before it is allowed to post; a
  live unbalanced journal is a GL integrity failure.

---

## FX

### `MISSING_FX_RATE`
- **Meaning**: a non-EUR event cannot be translated to management EUR —
  no reference rate on or before its date.
- **Compares**: event date / currency ↔ `raw_ecb.fx_rates`.
- **Trigger**: `reference_fx_rate is null` after the as-of lookup.
- **Policy**: `OPEN_BREAK` / `CRITICAL`.
- **Finance action**: load the missing ECB rate; the event has no
  management-EUR value and is excluded from valued volume until fixed.

### `FX_RATE_OUTLIER`
- **Meaning**: the PSP settlement FX diverges materially from the ECB
  reference rate.
- **Compares**: PSP settlement FX ↔ ECB reference FX (as-of).
- **Trigger**: absolute variance ratio `> 3%`.
- **Policy**: `OPEN_BREAK` / `WARNING`.
- **Finance action**: check for a PSP pricing error or a stale reference
  rate; quantify the FX cost.

---

## Product mapping

### `UNMAPPED_PRODUCT`
- **Meaning**: an invoice references a product the catalog does not
  know.
- **Compares**: Billing invoice `product_id` ↔ `stg_billing__products`.
- **Trigger**: `product_id` does not resolve.
- **Policy**: `OPEN_BREAK` / `WARNING`.
- **Finance action**: map the product; until then the amount cannot be
  attributed to a product dimension in `mart_finance_daily` and the
  daily report is incomplete for that slice.
