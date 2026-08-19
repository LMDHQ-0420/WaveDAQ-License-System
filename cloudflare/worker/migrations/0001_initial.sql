CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS licenses (
  id TEXT PRIMARY KEY,
  code_hash TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'unused' CHECK (status IN ('unused', 'active', 'revoked')),
  expires_at TEXT,
  offline_grace_days INTEGER NOT NULL DEFAULT 30,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS license_products (
  license_id TEXT NOT NULL REFERENCES licenses(id),
  product_id TEXT NOT NULL REFERENCES products(id),
  version_ranges_json TEXT NOT NULL,
  platforms_json TEXT NOT NULL,
  features_json TEXT NOT NULL DEFAULT '[]',
  PRIMARY KEY (license_id, product_id)
);

CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY,
  public_key TEXT NOT NULL UNIQUE,
  fingerprint TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS activations (
  license_id TEXT PRIMARY KEY REFERENCES licenses(id),
  device_id TEXT NOT NULL REFERENCES devices(id),
  activated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (license_id) REFERENCES licenses(id)
);

CREATE TABLE IF NOT EXISTS releases (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id),
  version TEXT NOT NULL,
  platform TEXT NOT NULL,
  asset_url TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  signature TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'hidden')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(product_id, version, platform)
);

CREATE INDEX IF NOT EXISTS idx_licenses_code_hash ON licenses(code_hash);
CREATE INDEX IF NOT EXISTS idx_releases_product ON releases(product_id, status);
