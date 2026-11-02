-- Consent-based email contact verification.
-- Apply only after reviewing on a Neon temporary branch.
CREATE TABLE contact_preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL UNIQUE REFERENCES cases(id) ON DELETE CASCADE,
  email_ciphertext TEXT NOT NULL,
  email_lookup_hash TEXT NOT NULL,
  consent_version TEXT NOT NULL,
  consent_at TIMESTAMPTZ NOT NULL,
  verification_token_hash TEXT,
  verification_expires_at TIMESTAMPTZ,
  verified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_contact_preferences_verification
  ON contact_preferences(verification_token_hash)
  WHERE verification_token_hash IS NOT NULL;
