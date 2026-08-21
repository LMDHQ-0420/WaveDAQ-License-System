CREATE TABLE IF NOT EXISTS admin_login_attempts (
  client_hash TEXT PRIMARY KEY,
  failures INTEGER NOT NULL DEFAULT 0,
  first_failed_at TEXT NOT NULL,
  last_failed_at TEXT NOT NULL,
  blocked_until TEXT
);

CREATE INDEX IF NOT EXISTS idx_admin_login_attempts_last_failed_at
  ON admin_login_attempts(last_failed_at);
