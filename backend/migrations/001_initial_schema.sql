-- CryptoResgate initial PostgreSQL schema
-- Apply through a reviewed Neon migration; do not run destructive statements here.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS cases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  public_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'submitted'
    CHECK (status IN ('submitted','triage','needs_information','under_review','eligible','ineligible','in_recovery','recovered','closed')),
  network TEXT NOT NULL,
  transaction_hash TEXT NOT NULL,
  asset_contract TEXT,
  reported_issue TEXT NOT NULL,
  description TEXT,
  contact_ciphertext TEXT,
  contact_lookup_hash TEXT,
  contact_channel TEXT CHECK (contact_channel IS NULL OR contact_channel IN ('email','phone','telegram','other')),
  contact_consent_at TIMESTAMPTZ,
  privacy_notice_version TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (network, transaction_hash)
);
CREATE TABLE IF NOT EXISTS case_evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  evidence_type TEXT NOT NULL CHECK (evidence_type IN ('transaction','explorer','exchange_response','user_document','analysis','other')),
  source_url TEXT,
  content JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_public BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS wallet_proofs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  wallet_address TEXT NOT NULL,
  chain_id BIGINT,
  message_nonce_hash TEXT NOT NULL UNIQUE,
  signed_message TEXT NOT NULL,
  signature TEXT NOT NULL,
  verified BOOLEAN NOT NULL DEFAULT FALSE,
  signed_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS consents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  consent_type TEXT NOT NULL CHECK (consent_type IN ('privacy','analysis','contact','service_terms','fee_agreement','data_sharing')),
  document_version TEXT NOT NULL,
  accepted BOOLEAN NOT NULL,
  accepted_at TIMESTAMPTZ,
  source_ip_hash TEXT,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS case_analyses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  model TEXT,
  classification TEXT NOT NULL CHECK (classification IN ('possible','unlikely','insufficient_data','requires_human_review')),
  confidence NUMERIC(5,4) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  findings JSONB NOT NULL DEFAULT '{}'::jsonb,
  limitations TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS audit_events (
  id BIGSERIAL PRIMARY KEY,
  case_id UUID REFERENCES cases(id) ON DELETE SET NULL,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('system','user','operator','mcp_client')),
  actor_ref TEXT,
  action TEXT NOT NULL,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cases_status_created ON cases(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_tx_hash ON cases(transaction_hash);
CREATE INDEX IF NOT EXISTS idx_evidence_case_created ON case_evidence(case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_consents_case_type ON consents(case_id, consent_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_case_created ON audit_events(case_id, created_at DESC);
