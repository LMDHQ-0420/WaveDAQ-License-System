import { error, body, json, requireAdmin } from "./http";
import { sha256, signLicense } from "./crypto";
import type { Env, LicenseDocument, ProductPermission } from "./types";

interface ActivateRequest { activation_code: string; device_id: string; device_public_key: string; fingerprint?: string; }
interface CreateLicenseRequest { license_id?: string; activation_code: string; expires_at?: string | null; offline_grace_days?: number; products: ProductPermission[]; }
interface CreateProductRequest { id: string; name: string; description?: string; }
interface CreateReleaseRequest { id: string; product_id: string; version: string; platform: string; asset_url: string; sha256: string; signature?: string | null; }

function id(prefix: string): string { return `${prefix}_${crypto.randomUUID().replaceAll("-", "")}`; }

async function buildLicense(env: Env, licenseId: string, deviceId: string, publicKey: string): Promise<LicenseDocument> {
  const license = await env.DB.prepare("SELECT id, expires_at, offline_grace_days FROM licenses WHERE id = ? AND status = 'active'").bind(licenseId).first<{ id: string; expires_at: string | null; offline_grace_days: number }>();
  if (!license) throw new Error("授权不存在或已失效");
  const rows = await env.DB.prepare("SELECT product_id, version_ranges_json, platforms_json, features_json FROM license_products WHERE license_id = ?").bind(licenseId).all<{ product_id: string; version_ranges_json: string; platforms_json: string; features_json: string }>();
  const products = rows.results.map((row) => ({ product_id: row.product_id, version_ranges: JSON.parse(row.version_ranges_json), platforms: JSON.parse(row.platforms_json), features: JSON.parse(row.features_json) }));
  if (!env.LICENSE_SIGNING_PRIVATE_KEY) throw new Error("服务端未配置签名私钥");
  const unsigned: Omit<LicenseDocument, "signature"> = { schema_version: "1", license_id: license.id, device_id: deviceId, device_public_key: publicKey, issued_at: new Date().toISOString(), expires_at: license.expires_at, offline_grace_days: license.offline_grace_days, products };
  return { ...unsigned, signature: await signLicense(unsigned, env.LICENSE_SIGNING_PRIVATE_KEY) };
}

async function activate(request: Request, env: Env): Promise<Response> {
  const input = await body<ActivateRequest>(request);
  if (!input.activation_code || !input.device_id || !input.device_public_key) return error("缺少激活参数");
  const codeHash = await sha256(input.activation_code.trim());
  const license = await env.DB.prepare("SELECT id, status FROM licenses WHERE code_hash = ?").bind(codeHash).first<{ id: string; status: string }>();
  if (!license) return error("激活码无效", 403);
  if (license.status !== "unused") return error("激活码已使用或已撤销", 409);
  const existingDevice = await env.DB.prepare("SELECT id FROM devices WHERE public_key = ? AND status = 'active'").bind(input.device_public_key).first<{ id: string }>();
  if (existingDevice && existingDevice.id !== input.device_id) return error("设备公钥已绑定其他设备", 409);
  const statements = [
    env.DB.prepare("INSERT OR IGNORE INTO devices (id, public_key, fingerprint) VALUES (?, ?, ?)").bind(input.device_id, input.device_public_key, input.fingerprint ?? null),
    env.DB.prepare("UPDATE licenses SET status = 'active' WHERE id = ? AND status = 'unused'").bind(license.id),
    env.DB.prepare("INSERT INTO activations (license_id, device_id) VALUES (?, ?)").bind(license.id, input.device_id)
  ];
  await env.DB.batch(statements);
  try { return json({ license: await buildLicense(env, license.id, input.device_id, input.device_public_key) }); }
  catch (e) { return error(e instanceof Error ? e.message : "授权签发失败", 500); }
}

async function releases(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const licenseId = url.searchParams.get("license_id");
  const deviceId = url.searchParams.get("device_id");
  if (!licenseId || !deviceId) return error("缺少授权参数");
  const valid = await env.DB.prepare("SELECT 1 FROM activations a JOIN licenses l ON l.id = a.license_id JOIN devices d ON d.id = a.device_id WHERE a.license_id = ? AND a.device_id = ? AND l.status = 'active' AND d.status = 'active'").bind(licenseId, deviceId).first();
  if (!valid) return error("授权无效", 403);
  const rows = await env.DB.prepare("SELECT r.id, r.product_id, r.version, r.platform, r.asset_url, r.sha256, r.signature FROM releases r JOIN license_products lp ON lp.product_id = r.product_id WHERE lp.license_id = ? AND r.status = 'active'").bind(licenseId).all();
  return json({ releases: rows.results });
}

async function admin(request: Request, env: Env, path: string): Promise<Response> {
  const denied = requireAdmin(request, env); if (denied) return denied;
  if (request.method === "POST" && path === "/products") {
    const input = await body<CreateProductRequest>(request);
    if (!input.id || !input.name) return error("缺少产品字段");
    await env.DB.prepare("INSERT INTO products (id, name, description) VALUES (?, ?, ?)").bind(input.id, input.name, input.description ?? "").run();
    return json({ id: input.id }, 201);
  }
  if (request.method === "POST" && path === "/licenses") {
    const input = await body<CreateLicenseRequest>(request);
    if (!input.activation_code || !input.products?.length) return error("缺少激活码或产品权限");
    const licenseId = input.license_id ?? id("lic");
    const hash = await sha256(input.activation_code.trim());
    await env.DB.prepare("INSERT INTO licenses (id, code_hash, expires_at, offline_grace_days) VALUES (?, ?, ?, ?)").bind(licenseId, hash, input.expires_at ?? null, input.offline_grace_days ?? 30).run();
    await env.DB.batch(input.products.map((product) => env.DB.prepare("INSERT INTO license_products (license_id, product_id, version_ranges_json, platforms_json, features_json) VALUES (?, ?, ?, ?, ?)").bind(licenseId, product.product_id, JSON.stringify(product.version_ranges), JSON.stringify(product.platforms), JSON.stringify(product.features ?? []))));
    return json({ license_id: licenseId }, 201);
  }
  if (request.method === "POST" && path === "/releases") {
    const input = await body<CreateReleaseRequest>(request);
    await env.DB.prepare("INSERT INTO releases (id, product_id, version, platform, asset_url, sha256, signature) VALUES (?, ?, ?, ?, ?, ?, ?)").bind(input.id, input.product_id, input.version, input.platform, input.asset_url, input.sha256, input.signature ?? null).run();
    return json({ id: input.id }, 201);
  }
  if (request.method === "GET" && path === "/licenses") {
    const rows = await env.DB.prepare("SELECT id, status, expires_at, created_at FROM licenses ORDER BY created_at DESC LIMIT 200").all();
    return json({ licenses: rows.results });
  }
  const revokeLicense = path.match(/^\/licenses\/([^/]+)\/revoke$/);
  if (request.method === "POST" && revokeLicense) {
    await env.DB.prepare("UPDATE licenses SET status = 'revoked' WHERE id = ?").bind(revokeLicense[1]).run();
    return json({ status: "revoked", license_id: revokeLicense[1] });
  }
  const revokeDevice = path.match(/^\/devices\/([^/]+)\/revoke$/);
  if (request.method === "POST" && revokeDevice) {
    await env.DB.prepare("UPDATE devices SET status = 'revoked' WHERE id = ?").bind(revokeDevice[1]).run();
    return json({ status: "revoked", device_id: revokeDevice[1] });
  }
  return error("管理接口不存在", 404);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/api/activate" && request.method === "POST") return await activate(request, env);
      if (url.pathname === "/api/releases" && request.method === "GET") return await releases(request, env);
      if (url.pathname.startsWith("/api/admin/")) return await admin(request, env, url.pathname.replace("/api/admin", ""));
      return error("Not Found", 404);
    } catch (e) {
      return error(e instanceof Error ? e.message : "服务器错误", 500);
    }
  }
};
