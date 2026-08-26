-- Source-aligned RAW schemas. Each schema represents an independent upstream system.
-- The landing layer is intentionally permissive: it stores what upstream delivered.

create schema if not exists raw_billing;
create schema if not exists raw_psp;
create schema if not exists raw_bank;
create schema if not exists raw_accounting;
create schema if not exists raw_ecb;