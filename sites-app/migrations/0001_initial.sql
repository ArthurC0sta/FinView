PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL COLLATE NOCASE UNIQUE,
  display_name TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS sessions_user_expires_idx ON sessions(user_id, expires_at);

CREATE TABLE IF NOT EXISTS login_codes (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL COLLATE NOCASE,
  code_hash TEXT NOT NULL,
  request_ip_hash TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0 AND attempts <= 5),
  expires_at TEXT NOT NULL,
  consumed_at TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS login_codes_email_created_idx ON login_codes(email, created_at DESC);
CREATE INDEX IF NOT EXISTS login_codes_ip_created_idx ON login_codes(request_ip_hash, created_at DESC);

CREATE TABLE IF NOT EXISTS businesses (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  segment TEXT NOT NULL DEFAULT '',
  activity TEXT NOT NULL DEFAULT '',
  city TEXT NOT NULL DEFAULT '',
  state TEXT NOT NULL DEFAULT '',
  legal_form TEXT NOT NULL DEFAULT '',
  offering_type TEXT NOT NULL DEFAULT '',
  tax_regime TEXT NOT NULL DEFAULT '',
  employees_count INTEGER CHECK (employees_count IS NULL OR employees_count >= 0),
  business_goal TEXT NOT NULL DEFAULT '',
  profile_updated_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS business_profile_assessments (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  questionnaire_version TEXT NOT NULL DEFAULT '1.0',
  maturity_answers_json TEXT NOT NULL DEFAULT '{}',
  preferences_json TEXT NOT NULL DEFAULT '{}',
  score INTEGER CHECK (score IS NULL OR score BETWEEN 0 AND 26),
  recommended_level TEXT CHECK (recommended_level IN ('', 'essential', 'managerial', 'complete')),
  determining_factors_json TEXT NOT NULL DEFAULT '[]',
  is_boundary INTEGER NOT NULL DEFAULT 0 CHECK (is_boundary IN (0, 1)),
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'completed')),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
  completed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS profile_current_business_idx
  ON business_profile_assessments(business_id) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS managerial_categories (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  group_name TEXT NOT NULL CHECK (group_name IN (
    'revenue', 'taxes_fees', 'variable_direct', 'fixed', 'administrative',
    'investment', 'loan', 'contribution', 'withdrawal', 'transfer', 'unclassified'
  )),
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  is_system INTEGER NOT NULL DEFAULT 0 CHECK (is_system IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (business_id, name)
);

CREATE TABLE IF NOT EXISTS import_batches (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  uploaded_by_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  original_name TEXT NOT NULL,
  sanitized_name TEXT NOT NULL,
  file_format TEXT NOT NULL CHECK (file_format IN ('csv', 'xls', 'ofx', 'ofc', 'pdf', 'cnab')),
  file_hash TEXT NOT NULL,
  file_size INTEGER NOT NULL CHECK (file_size > 0 AND file_size <= 10485760),
  r2_key TEXT,
  status TEXT NOT NULL CHECK (status IN (
    'received', 'validating', 'awaiting_review', 'confirmed', 'processed',
    'partially_processed', 'rejected', 'cancelled', 'expired'
  )),
  total_rows INTEGER NOT NULL DEFAULT 0 CHECK (total_rows BETWEEN 0 AND 1000),
  valid_rows INTEGER NOT NULL DEFAULT 0,
  invalid_rows INTEGER NOT NULL DEFAULT 0,
  duplicate_rows INTEGER NOT NULL DEFAULT 0,
  error_message TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  confirmed_at TEXT,
  processed_at TEXT,
  UNIQUE (business_id, file_hash)
);

CREATE INDEX IF NOT EXISTS import_batches_business_created_idx
  ON import_batches(business_id, created_at DESC);

CREATE TABLE IF NOT EXISTS import_rows (
  id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
  source_row INTEGER NOT NULL CHECK (source_row > 0),
  transaction_date TEXT,
  description TEXT NOT NULL DEFAULT '',
  amount_cents INTEGER CHECK (amount_cents IS NULL OR amount_cents > 0),
  direction TEXT CHECK (direction IN ('inflow', 'outflow')),
  external_id TEXT NOT NULL DEFAULT '',
  fingerprint TEXT NOT NULL,
  is_valid INTEGER NOT NULL DEFAULT 1 CHECK (is_valid IN (0, 1)),
  is_duplicate INTEGER NOT NULL DEFAULT 0 CHECK (is_duplicate IN (0, 1)),
  suggested_category_id TEXT REFERENCES managerial_categories(id) ON DELETE SET NULL,
  suggestion_confidence INTEGER CHECK (suggestion_confidence IS NULL OR suggestion_confidence BETWEEN 0 AND 100),
  confirmed_category_id TEXT REFERENCES managerial_categories(id) ON DELETE SET NULL,
  transaction_id TEXT UNIQUE,
  decision TEXT NOT NULL DEFAULT 'pending' CHECK (decision IN ('pending', 'accepted', 'excluded')),
  error_message TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (batch_id, fingerprint)
);

CREATE TABLE IF NOT EXISTS financial_transactions (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
  direction TEXT NOT NULL CHECK (direction IN ('inflow', 'outflow')),
  name TEXT NOT NULL,
  amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
  transaction_date TEXT NOT NULL,
  category_id TEXT NOT NULL REFERENCES managerial_categories(id) ON DELETE RESTRICT,
  status TEXT NOT NULL DEFAULT 'realized' CHECK (status IN ('realized', 'planned')),
  certainty TEXT NOT NULL DEFAULT 'confirmed' CHECK (certainty IN ('confirmed', 'estimated')),
  recurrence TEXT NOT NULL DEFAULT 'variable' CHECK (recurrence IN ('fixed', 'variable')),
  priority TEXT NOT NULL DEFAULT 'essential' CHECK (priority IN ('essential', 'important', 'superfluous')),
  source TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'recurrence', 'import')),
  notes TEXT NOT NULL DEFAULT '',
  import_row_id TEXT UNIQUE REFERENCES import_rows(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS transactions_business_date_idx
  ON financial_transactions(business_id, transaction_date DESC);
CREATE INDEX IF NOT EXISTS transactions_business_direction_date_idx
  ON financial_transactions(business_id, direction, transaction_date DESC);

CREATE TABLE IF NOT EXISTS financial_goals (
  id TEXT PRIMARY KEY,
  business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  target_amount_cents INTEGER NOT NULL CHECK (target_amount_cents > 0),
  saved_amount_cents INTEGER NOT NULL DEFAULT 0 CHECK (
    saved_amount_cents >= 0 AND saved_amount_cents <= target_amount_cents
  ),
  target_date TEXT,
  goal_type TEXT NOT NULL DEFAULT 'saving' CHECK (goal_type IN ('saving', 'debt', 'investment', 'purchase', 'emergency')),
  priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed')),
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
