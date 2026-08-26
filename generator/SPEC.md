# Synthetic Source Generator Specification v1.0

## Purpose

The generator emulates the private source systems that a finance analytics team would normally
receive from Billing, a payment service provider, a bank, and Accounting. It does **not** generate
the production/demo ECB source: ECB remains a separate external extractor. A deterministic FX
fixture is allowed only for CI and local tests.

The generator is an upstream-system simulator, not a transformation layer. It must emit source-like
records in the RAW contract shape and must not pre-compute dbt reconciliation statuses.

## Determinism contract

Given the same `seed`, configuration, product catalog, date range, and FX reference input, the
result must be byte-for-byte stable after canonical CSV ordering. IDs must be deterministic and
must not rely on wall-clock time, UUID4, Faker internals, or unordered collection iteration.

Use one local pseudo-random generator seeded from `seed`; do not use the global random state.
Stable source IDs use zero-padded sequences within each entity type, for example `INV-000001`.

The dataset run ID is derived from the inputs, conceptually:

`SYN-{seed}-{start}-{end}-{scenario}`

The generator writes the exact effective configuration into the output directory.

## Output boundary

Synthetic output contains these nine tables:

1. `raw_billing.products`
2. `raw_billing.subscriptions`
3. `raw_billing.invoices`
4. `raw_psp.payment_attempts`
5. `raw_psp.financial_events`
6. `raw_psp.settlements`
7. `raw_psp.settlement_items`
8. `raw_bank.statement_transactions`
9. `raw_accounting.journal_lines`

`raw_ecb.fx_rates` is loaded by the ECB extractor. In CI, the extractor may run in fixture mode.

The generator writes source extracts, not SQL inserts:

```text
data/generated/<run_id>/
├── billing/
│   ├── products.csv
│   ├── subscriptions.csv
│   └── invoices.csv
├── psp/
│   ├── payment_attempts.csv
│   ├── financial_events.csv
│   ├── settlements.csv
│   └── settlement_items.csv
├── bank/
│   └── statement_transactions.csv
├── accounting/
│   └── journal_lines.csv
├── _effective_config.yml
├── _manifest.json
└── _expected_exceptions.json   # only when anomaly scenario is enabled
```

The later ingestion component is responsible for `_loaded_at`, `_batch_id`, and idempotent UPSERT
semantics. Source extracts contain business/source fields only.

## Generation order

Generation order is fixed because later source systems depend on earlier business events:

1. Product catalog.
2. Pseudonymous customers and subscriptions.
3. Recurring invoices.
4. Payment attempts.
5. Successful CAPTURE financial events.
6. Natural REFUND and CHARGEBACK events.
7. PSP settlement items and daily settlement batches.
8. Bank statement transactions for paid settlements.
9. Accounting journals for financial events and settlements.
10. Optional anomaly injection.
11. Manifests and canonical CSV sort/write.

## Product and subscription behavior

Products are read from `generator/catalog.yml`; selection weights must sum to 1 within floating
point tolerance. The product source row is generated directly from the catalog.

Customer identifiers are pseudonymous (`CUST-######`). No names, emails, addresses, card numbers,
IP addresses, or other PII are generated.

Each generated customer has at most one v1 subscription. Subscription start dates are distributed
before and inside the requested data window so monthly renewals occur throughout the range.
Subscription product assignment follows catalog weights.

Natural states include ACTIVE, PAST_DUE, and CANCELLED. A CANCELLED subscription must have a
`cancelled_at`; non-cancelled subscriptions must not.

## Invoice behavior

A monthly subscription invoices on its billing-anchor day; annual plans invoice on their annual
anchor. Invoices are generated only when the invoice date falls inside the configured event range.

For v1, tax defaults to zero. Invoice monetary values are integer minor units. The clean generator
always satisfies `total_minor = subtotal_minor + tax_minor`.

A successfully collected invoice becomes PAID. Exhausted payment retries become UNCOLLECTIBLE.
Recent/unprocessed invoices may remain OPEN. VOID is supported by the contract but does not need
to be generated in the first implementation unless explicitly configured.

## Payment behavior

Every payable invoice receives at least one payment attempt. The first attempt may decline according
to configuration. Declined attempts may retry up to `max_attempts`.

A clean invoice has at most one SUCCEEDED attempt. A SUCCEEDED attempt produces exactly one CAPTURE
event. The capture amount and currency equal the invoice total and currency in the clean scenario.

Failed attempts are normal business behavior and do not create monetary financial events.

## Refund behavior

A configurable share of captures receives a refund after the configured delay. Refund amount is a
configured fraction of the original capture. RAW refund amounts remain positive; the negative sign
is a downstream staging responsibility.

Clean data guarantees cumulative refunds do not exceed the original capture. Multiple partial
refunds are allowed by the data contract, though the first implementation may generate at most one
natural refund per capture before explicit multi-refund coverage is added.

## Chargeback behavior

A small configurable share of eligible captures receives a chargeback after the minimum delay.
Chargebacks reference the original capture and use the same transaction currency. The first
implementation avoids selecting fully refunded captures for natural chargebacks.

## FX reference and PSP FX

The generator consumes a normalized reference FX provider only as a market anchor for synthetic PSP
rates and event-side accounting amounts. In CI this is a deterministic fixture; in demo mode it may
be the cache produced by the real ECB extractor.

Reference orientation supplied to generator logic is `EUR per 1 unit of transaction currency`.
The official `raw_ecb.fx_rates` table preserves the opposite ECB orientation and is normalized later
by dbt staging.

PSP FX is generated independently from the reference by applying a deterministic spread within the
configured basis-point range. EUR transactions have `psp_fx_rate = 1.00000000`.

Normal PSP-vs-reference FX differences are expected and must not be engineered to equal zero.

## Settlement behavior

Each CAPTURE/REFUND/CHARGEBACK receives an eligible settlement date from the configured 1–4 day
delay distribution. Events are grouped into EUR payout batches by settlement date.

Settlement-item conventions:

- `transaction_amount_minor` is always positive.
- `settlement_gross_eur_minor` is positive for CAPTURE and negative for REFUND/CHARGEBACK.
- The v1 PSP fee is charged on CAPTURE items only: variable percentage plus fixed EUR fee.
- REFUND and CHARGEBACK items have zero allocated PSP fee in v1; additional dispute fees are out of scope.
- `settlement_net_eur_minor = settlement_gross_eur_minor - fee_eur_minor`.

Settlement-header conventions:

- `gross_amount_minor = sum(settlement_gross_eur_minor)`.
- `fee_amount_minor = sum(fee_eur_minor)`.
- `net_payout_minor = gross_amount_minor - fee_amount_minor`.
- v1 emits only positive payout batches. Negative net event balances roll into the next positive batch.
- clean paid settlements receive a unique `bank_reference`.

## Bank behavior

Every clean PAID settlement produces exactly one EUR CREDIT / BOOKED bank transaction after the
configured 0–2 day posting delay. `payment_reference` exactly equals the settlement `bank_reference`.
The amount exactly equals `net_payout_minor` in clean data.

The bank source may contain other directions/statuses in future, but unrelated cash flows are not
needed for v1.

## Accounting behavior

Accounting uses a deliberately limited chart of accounts:

- 1100 BANK
- 1200 PSP_CLEARING
- 4000 SALES_CLEARING
- 6100 PAYMENT_PROCESSING_FEES
- 6200 CHARGEBACK_LOSS
- 6300 CUSTOMER_REFUNDS

All clean POSTED journal entries balance to the cent.

Event journals use standardized reporting EUR value from the reference FX provider:

- CAPTURE: Dr PSP_CLEARING / Cr SALES_CLEARING.
- REFUND: Dr CUSTOMER_REFUNDS / Cr PSP_CLEARING.
- CHARGEBACK: Dr CHARGEBACK_LOSS / Cr PSP_CLEARING.

Settlement journals use actual PSP EUR values:

- Dr BANK = settlement net payout.
- Dr PAYMENT_PROCESSING_FEES = settlement fee.
- Cr PSP_CLEARING = settlement gross amount.

Because event journals use reporting FX while settlements use PSP FX, the project does not assert
that the aggregate PSP_CLEARING account closes to zero. FX gain/loss accounting and full GL close
are explicitly outside v1 scope; reconciliation validates the expected journal for each referenced
business object.

## Natural behavior versus injected anomalies

The clean scenario must still contain realistic complexity: declined attempts, retries, partial
refunds, chargebacks, weekend/holiday FX lookback, multi-item settlement batches, and posting delays.
These are not control failures.

`with_anomalies` starts from a valid clean dataset and then applies deterministic mutations. It must
not use random ad-hoc corruption. Each injected case is selected by stable hashing of `(seed,
anomaly_type, ordinal)` over eligible records.

The anomaly layer emits `_expected_exceptions.json`, which is a test oracle and is **never loaded to
RAW**. It contains anomaly type, affected source identifiers, intended finance exception, and any
expected secondary exception when unavoidable.

Required anomaly mutations:

| Mutation | Intended exception behavior |
| --- | --- |
| Second successful attempt + settled capture for one invoice | `DUPLICATE_CAPTURE` |
| Change capture amount while keeping the rest of its lifecycle internally consistent | `CAPTURE_AMOUNT_MISMATCH` |
| Add refunds whose cumulative value exceeds capture | `OVER_REFUND` |
| Leave an event older than 5 days without a settlement item | `MISSING_SETTLEMENT` |
| Mutate settlement header while downstream bank/accounting follow the header | `SETTLEMENT_TOTAL_MISMATCH` |
| Remove bank row for a settlement older than 2 days | `MISSING_BANK_RECEIPT` |
| Change bank amount only | `BANK_AMOUNT_MISMATCH` |
| Remove expected posted accounting journal | `MISSING_LEDGER_POSTING` |
| Mutate one journal line so debits and credits differ | `UNBALANCED_JOURNAL` (takes precedence over amount mismatch) |
| Replace one invoice product_id with a nonexistent identifier | `UNMAPPED_PRODUCT` |
| Make one early non-EUR event impossible to resolve to a prior reference rate in the CI fixture | `MISSING_FX_RATE` |
| Apply >3% PSP-vs-reference FX deviation and recompute the rest of lifecycle consistently | `FX_RATE_OUTLIER` |

Anomaly isolation matters: whenever possible, all dependent source rows must be recomputed so the
mutation triggers its intended control rather than a cascade of unrelated failures.

## Manifest contract

`_manifest.json` records run ID, seed, scenario, date range, row counts per table, min/max business
and loaded dates where applicable, catalog hash, config hash, and generator version.

`_expected_exceptions.json` is present only when `scenario=with_anomalies` and
`include_control_manifest=true`.

## Scale profiles

The first implementation must support at least:

- CI profile: ~5,000 invoices over ~30 days; fast enough for pull-request tests.
- Demo profile: ~100,000–250,000 invoices over ~365 days; enough volume to justify incremental dbt
  models and orchestration without pretending to be big data.

Scale is achieved through customer/subscription volume, not by duplicating rows after generation.

## Non-goals

The generator does not model PII, VAT engines, IFRS 15 revenue recognition, fraud scoring, card
credentials, full bank statements, full ERP/general-ledger behavior, tax jurisdiction, or PSP dispute
fees. These exclusions are deliberate scope controls, not missing implementation.
