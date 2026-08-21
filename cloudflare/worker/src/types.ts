export interface Env {
  DB: D1Database;
  LICENSE_SIGNING_PRIVATE_KEY?: string;
  ADMIN_TOKEN?: string;
  ADMIN_PASSWORD_HASH?: string;
  GITHUB_TOKEN?: string;
}

export interface ProductPermission {
  product_id: string;
  platforms: string[];
}

export interface LicenseDocument {
  schema_version: "1";
  license_id: string;
  device_id: string;
  device_public_key: string;
  issued_at: string;
  expires_at: string | null;
  products: ProductPermission[];
  signature: string;
}

export interface LicenseRow {
  id: string;
  expires_at: string | null;
}
