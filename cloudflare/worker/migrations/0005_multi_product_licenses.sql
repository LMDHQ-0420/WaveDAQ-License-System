ALTER TABLE products ADD COLUMN github_repository TEXT NOT NULL DEFAULT '';
ALTER TABLE licenses ADD COLUMN name TEXT NOT NULL DEFAULT '';
ALTER TABLE licenses ADD COLUMN term TEXT NOT NULL DEFAULT '永久';

CREATE INDEX IF NOT EXISTS idx_license_products_product ON license_products(product_id, license_id);
