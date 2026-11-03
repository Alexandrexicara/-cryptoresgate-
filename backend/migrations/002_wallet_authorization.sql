-- Additive, non-destructive wallet proof and service authorization tables.
-- Safe to apply after 001_initial_schema.sql; no existing rows or tables are changed.
CREATE TABLE IF NOT EXISTS wallet_challenges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  wallet_address TEXT NOT NULL,
  chain_id BIGINT NOT NULL CHECK (chain_id > 0),
  nonce_hash TEXT NOT NULL UNIQUE,
  message TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  verified_at TIMESTAMPTZ,
  signature TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wallet_challenges_case_created
  ON wallet_challenges(case_id, created_at DESC);

CREATE TABLE IF NOT EXISTS case_authorizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  wallet_proof_id UUID NOT NULL REFERENCES wallet_proofs(id),
  institution TEXT NOT NULL,
  authorized_scope TEXT[] NOT NULL,
  service_fee_bps INTEGER NOT NULL CHECK (service_fee_bps BETWEEN 0 AND 10000),
  terms_version TEXT NOT NULL,
  accepted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_case_authorizations_case_created
  ON case_authorizations(case_id, created_at DESC);
