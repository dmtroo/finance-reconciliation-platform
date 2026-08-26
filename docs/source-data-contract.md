## Global conventions

- Source systems: Billing, PSP, Bank, Accounting, ECB.
- Functional/reporting currency: EUR.
- Supported transaction currencies: EUR, USD, GBP, PLN, SEK.
- Monetary values in RAW: integer minor units (`BIGINT`).
- FX precision: `NUMERIC(18,8)`.
- Technical timestamps: UTC `TIMESTAMPTZ`.
- Business dates: `DATE`.
- Every loaded RAW record has `_loaded_at` and `_batch_id`.
- No PII is generated or stored; `customer_id` is pseudonymous.
- RAW does not repair invalid business relationships or amounts.

## Source-of-truth matrix

| Concept | Source of truth |
| --- | --- |
| Product / subscription / invoice | Billing |
| Payment success / capture / refund / chargeback | PSP |
| PSP fee / payout / PSP FX | PSP settlement |
| Actual cash receipt | Bank |
| Accounting posting | Accounting |
| Standardized management FX | ECB |

A disagreement between authoritative systems becomes a downstream reconciliation exception; one
source is not silently overwritten with another.

## Tables and grain

| RAW table | Grain | Source key |
| --- | --- | --- |
| `raw_billing.products` | one sellable plan | `product_id` |
| `raw_billing.subscriptions` | one subscription | `subscription_id` |
| `raw_billing.invoices` | one issued invoice | `invoice_id` |
| `raw_psp.payment_attempts` | one attempt | `payment_attempt_id` |
| `raw_psp.financial_events` | one CAPTURE/REFUND/CHARGEBACK | `financial_event_id` |
| `raw_psp.settlements` | one payout batch | `settlement_id` |
| `raw_psp.settlement_items` | one event inside a settlement | `settlement_item_id` |
| `raw_bank.statement_transactions` | one bank statement line | `bank_transaction_id` |
| `raw_accounting.journal_lines` | one journal line | `journal_line_id` |
| `raw_ecb.fx_rates` | one currency/date observation | `(rate_date, currency)` |

## Controlled vocabularies

- Product family: `CORE_SECURITY`, `PRIVACY`, `IDENTITY`, `CONNECTIVITY`.
- Billing interval: `MONTH`, `YEAR`.
- Subscription status: `ACTIVE`, `PAST_DUE`, `CANCELLED`.
- Invoice status: `OPEN`, `PAID`, `VOID`, `UNCOLLECTIBLE`.
- Payment attempt status: `SUCCEEDED`, `DECLINED`, `CANCELLED`.
- Payment method: `CARD`, `PAYPAL`, `APPLE_PAY`, `GOOGLE_PAY`.
- Financial event type: `CAPTURE`, `REFUND`, `CHARGEBACK`.
- Settlement status: `PENDING`, `PAID`, `FAILED`.
- Bank direction: `CREDIT`, `DEBIT`.
- Bank status: `BOOKED`, `PENDING`.
- Journal status: `POSTED`, `DRAFT`, `REVERSED`.
- Accounting reference type: `FINANCIAL_EVENT`, `SETTLEMENT`.

## Monetary and sign conventions

Raw PSP financial-event amounts are unsigned. Staging creates signed amounts:

- CAPTURE -> positive.
- REFUND -> negative.
- CHARGEBACK -> negative.

PSP FX orientation is **EUR per one unit of transaction currency**. Raw ECB orientation is preserved
as **foreign-currency units per 1 EUR** and inverted in staging for reporting calculations.

## Timing rules used by later reconciliation controls

- Payment/financial event without settlement: PENDING through day 5; `MISSING_SETTLEMENT` after 5 days.
- PAID settlement without bank receipt: grace period 2 calendar days; then `MISSING_BANK_RECEIPT`.
- Exact EUR reconciliation tolerance: EUR 0.01.
- PSP-vs-reference FX deviation above 3%: `FX_RATE_OUTLIER` warning.
- For non-business-day FX, use latest available rate with `rate_date <= event_date`.

## Why RAW has few physical constraints

The source contract defines many logical requirements, but only source identity and ingestion metadata
are hard database constraints. Cross-system relationships are intentionally not PostgreSQL foreign
keys. A source row with an unknown product, missing downstream settlement, or invalid accounting
relationship must remain queryable so Finance can investigate it.

`dbt` is therefore responsible for observing and classifying violations rather than the database
rejecting them at ingest time.
