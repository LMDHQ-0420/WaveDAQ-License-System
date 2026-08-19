export interface Env {
  DB: D1Database;
  LICENSE_SCHEMA_VERSION: string;
  LICENSE_SIGNING_PRIVATE_KEY?: string;
  ADMIN_TOKEN?: string;
  GITHUB_TOKEN?: string;
}

export interface ProductPermission {
  product_id: string;
  version_ranges: string[];
  platforms: string[];
  features?: string[];
}

export interface LicenseDocument {
  schema_version: "1";
  license_id: string;
  device_id: string;
  device_public_key: string;
  issued_at: string;
  expires_at: string | null;
  offline_grace_days: number;
  products: ProductPermission[];
  metadata?: Record<string, string>;
  signature: string;
}

export interface LicenseRow {
  id: string;
  expires_at: string | null;
  offline_grace_days: number;
}
