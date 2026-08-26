-- Finance Reconciliation Platform — RAW source layer v1.0
--
-- Physical constraints intentionally stop at source identity and ingestion metadata.
-- Business constraints (accepted states, referential integrity, amount reconciliation,
-- timing rules, etc.) are observed by dbt rather than used to reject source rows.
-- This lets the warehouse retain bad-but-real source data for investigation.

create table if not exists raw_billing.products (
    product_id text primary key,
    product_name text,
    product_family text,
    billing_interval text,
    list_price_minor bigint,
    currency char(3),
    is_active boolean,
    created_at timestamptz,
    updated_at timestamptz,
    _loaded_at timestamptz not null,
    _batch_id text not null
);

create table if not exists raw_billing.subscriptions (
    subscription_id text primary key,
    customer_id text,
    product_id text,
    subscription_status text,
    started_at timestamptz,
    cancelled_at timestamptz,
    created_at timestamptz,
    updated_at timestamptz,
    _loaded_at timestamptz not null,
    _batch_id text not null
);

create table if not exists raw_billing.invoices (
    invoice_id text primary key,
    subscription_id text,
    customer_id text,
    product_id text,
    invoice_date date,
    due_date date,
    currency char(3),
    subtotal_minor bigint,
    tax_minor bigint,
    total_minor bigint,
    invoice_status text,
    created_at timestamptz,
    updated_at timestamptz,
    _loaded_at timestamptz not null,
    _batch_id text not null
);

create table if not exists raw_psp.payment_attempts (
    payment_attempt_id text primary key,
    invoice_id text,
    provider_customer_id text,
    attempted_at timestamptz,
    currency char(3),
    amount_minor bigint,
    payment_method_type text,
    status text,
    failure_code text,
    provider_transaction_id text,
    _loaded_at timestamptz not null,
    _batch_id text not null
);

create table if not exists raw_psp.financial_events (
    financial_event_id text primary key,
    event_type text,
    payment_attempt_id text,
    invoice_id text,
    original_capture_id text,
    event_at timestamptz,
    currency char(3),
    amount_minor bigint,
    provider_transaction_id text,
    _loaded_at timestamptz not null,
    _batch_id text not null
);

create table if not exists raw_psp.settlements (
    settlement_id text primary key,
    settlement_date date,
    settlement_currency char(3),
    gross_amount_minor bigint,
    fee_amount_minor bigint,
    net_payout_minor bigint,
    status text,
    bank_reference text,
    created_at timestamptz,
    _loaded_at timestamptz not null,
    _batch_id text not null
);

create table if not exists raw_psp.settlement_items (
    settlement_item_id text primary key,
    settlement_id text,
    financial_event_id text,
    transaction_currency char(3),
    transaction_amount_minor bigint,
    settlement_gross_eur_minor bigint,
    fee_eur_minor bigint,
    settlement_net_eur_minor bigint,
    psp_fx_rate numeric(18,8),
    _loaded_at timestamptz not null,
    _batch_id text not null
);

create table if not exists raw_bank.statement_transactions (
    bank_transaction_id text primary key,
    booking_date date,
    value_date date,
    direction text,
    currency char(3),
    amount_minor bigint,
    counterparty text,
    payment_reference text,
    status text,
    _loaded_at timestamptz not null,
    _batch_id text not null
);

create table if not exists raw_accounting.journal_lines (
    journal_line_id text primary key,
    journal_entry_id text,
    posting_date date,
    account_code text,
    account_name text,
    debit_eur_minor bigint,
    credit_eur_minor bigint,
    source_system text,
    source_reference_type text,
    source_reference text,
    journal_status text,
    created_at timestamptz,
    _loaded_at timestamptz not null,
    _batch_id text not null
);

create table if not exists raw_ecb.fx_rates (
    rate_date date not null,
    currency char(3) not null,
    units_per_eur numeric(18,8),
    _loaded_at timestamptz not null,
    _batch_id text not null,
    primary key (rate_date, currency)
);

-- Non-unique lookup indexes improve source validation and future staging joins without
-- asserting business relationships at the database layer.
create index if not exists idx_subscriptions_product_id
    on raw_billing.subscriptions (product_id);

create index if not exists idx_invoices_subscription_id
    on raw_billing.invoices (subscription_id);

create index if not exists idx_invoices_product_id
    on raw_billing.invoices (product_id);

create index if not exists idx_payment_attempts_invoice_id
    on raw_psp.payment_attempts (invoice_id);

create index if not exists idx_financial_events_invoice_id
    on raw_psp.financial_events (invoice_id);

create index if not exists idx_financial_events_payment_attempt_id
    on raw_psp.financial_events (payment_attempt_id);

create index if not exists idx_financial_events_original_capture_id
    on raw_psp.financial_events (original_capture_id);

create index if not exists idx_settlement_items_settlement_id
    on raw_psp.settlement_items (settlement_id);

create index if not exists idx_settlement_items_financial_event_id
    on raw_psp.settlement_items (financial_event_id);

create index if not exists idx_bank_payment_reference
    on raw_bank.statement_transactions (payment_reference);

create index if not exists idx_journal_lines_entry_id
    on raw_accounting.journal_lines (journal_entry_id);

create index if not exists idx_journal_lines_source_reference
    on raw_accounting.journal_lines (source_reference_type, source_reference);
