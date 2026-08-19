import { error, body, json, requireAdmin } from "./http";
import { sha256, signLicense, verifyEd25519 } from "./crypto";
import type { Env, LicenseDocument, ProductPermission } from "./types";

interface ActivateRequest { activation_code: string; device_id: string; device_public_key: string; fingerprint?: string; }
interface CreateLicenseRequest { license_id?: string; activation_code: string; expires_at?: string | null; offline_grace_days?: number; products: ProductPermission[]; }
interface CreateProductRequest { id: string; name: string; description?: string; }
interface CreateReleaseRequest { id: string; product_id: string; version: string; platform: string; asset_url: string; sha256: string; file_name: string; launch_path: string; signature?: string | null; }
interface DeviceAuth { licenseId: string; deviceId: string; publicKey: string; }

function id(prefix: string): string { return `${prefix}_${crypto.randomUUID().replaceAll("-", "")}`; }
function isExpired(value: string | null): boolean { return value !== null && Date.parse(value) <= Date.now(); }
function versionAllowed(version: string, ranges: string[]): boolean {
  return ranges.some((range) => range === "*" || range === version || (range.endsWith(".*") && version.startsWith(range.slice(0, -1))));
}
const PLATFORMS = new Set(["windows-x64", "macos-arm64", "macos-x64"]);
function validPermission(value: ProductPermission): boolean {
  return /^[a-z0-9][a-z0-9-]{1,63}$/.test(value.product_id) && Array.isArray(value.version_ranges) && value.version_ranges.length > 0 && value.version_ranges.every((item) => item === "*" || /^[0-9]+\.[0-9]+(?:\.[0-9]+|\.\*)$/.test(item)) && Array.isArray(value.platforms) && value.platforms.length > 0 && value.platforms.every((item) => PLATFORMS.has(item));
}
function trustedGithubAsset(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.hostname === "api.github.com" && /^\/repos\/LMDHQ-0420\/[^/]+\/releases\/assets\/[0-9]+$/.test(url.pathname);
  } catch { return false; }
}

async function buildLicense(env: Env, licenseId: string, deviceId: string, publicKey: string, allowUnused = false): Promise<LicenseDocument> {
  const statuses = allowUnused ? "('active', 'unused')" : "('active')";
  const license = await env.DB.prepare(`SELECT id, expires_at, offline_grace_days FROM licenses WHERE id = ? AND status IN ${statuses}`).bind(licenseId).first<{ id: string; expires_at: string | null; offline_grace_days: number }>();
  if (!license || isExpired(license.expires_at)) throw new Error("授权不存在、已失效或已过期");
  const rows = await env.DB.prepare("SELECT product_id, version_ranges_json, platforms_json, features_json FROM license_products WHERE license_id = ?").bind(licenseId).all<{ product_id: string; version_ranges_json: string; platforms_json: string; features_json: string }>();
  const products = rows.results.map((row) => ({ product_id: row.product_id, version_ranges: JSON.parse(row.version_ranges_json), platforms: JSON.parse(row.platforms_json), features: JSON.parse(row.features_json) }));
  if (!env.LICENSE_SIGNING_PRIVATE_KEY) throw new Error("服务端未配置签名私钥");
  const unsigned: Omit<LicenseDocument, "signature"> = { schema_version: "1", license_id: license.id, device_id: deviceId, device_public_key: publicKey, issued_at: new Date().toISOString(), expires_at: license.expires_at, offline_grace_days: license.offline_grace_days, products };
  return { ...unsigned, signature: await signLicense(unsigned, env.LICENSE_SIGNING_PRIVATE_KEY) };
}

async function authenticateDevice(request: Request, env: Env): Promise<DeviceAuth | Response> {
  const url = new URL(request.url);
  const licenseId = url.searchParams.get("license_id") ?? "";
  const deviceId = request.headers.get("x-device-id") ?? "";
  const timestamp = request.headers.get("x-device-timestamp") ?? "";
  const nonce = request.headers.get("x-device-nonce") ?? "";
  const signature = request.headers.get("x-device-signature") ?? "";
  if (!licenseId || !deviceId || !timestamp || !/^[a-f0-9]{32}$/.test(nonce) || !signature) return error("缺少设备认证参数", 401);
  const epoch = Number(timestamp);
  if (!Number.isFinite(epoch) || Math.abs(Date.now() / 1000 - epoch) > 300) return error("设备请求已过期", 401);
  const row = await env.DB.prepare("SELECT d.public_key, l.expires_at FROM activations a JOIN licenses l ON l.id = a.license_id JOIN devices d ON d.id = a.device_id WHERE a.license_id = ? AND a.device_id = ? AND l.status = 'active' AND d.status = 'active'").bind(licenseId, deviceId).first<{ public_key: string; expires_at: string | null }>();
  if (!row || isExpired(row.expires_at)) return error("授权无效或已过期", 403);
  const message = `${request.method}\n${url.pathname}\n${licenseId}\n${deviceId}\n${timestamp}\n${nonce}`;
  try { if (!await verifyEd25519(row.public_key, message, signature)) return error("设备签名无效", 401); }
  catch { return error("设备签名格式无效", 401); }
  try {
    await env.DB.batch([
      env.DB.prepare("INSERT INTO request_nonces (nonce, device_id) VALUES (?, ?)").bind(nonce, deviceId),
      env.DB.prepare("DELETE FROM request_nonces WHERE created_at < datetime('now', '-10 minutes')")
    ]);
  } catch { return error("设备请求已被使用", 409); }
  await env.DB.prepare("UPDATE devices SET last_seen_at = CURRENT_TIMESTAMP WHERE id = ?").bind(deviceId).run();
  return { licenseId, deviceId, publicKey: row.public_key };
}

async function activate(request: Request, env: Env): Promise<Response> {
  const input = await body<ActivateRequest>(request);
  if (!input.activation_code || !/^dev_[a-f0-9]{32}$/.test(input.device_id) || !/^[A-Za-z0-9_-]{43}$/.test(input.device_public_key)) return error("激活参数格式无效");
  const codeHash = await sha256(input.activation_code.trim().toUpperCase());
  const license = await env.DB.prepare("SELECT id, status, expires_at FROM licenses WHERE code_hash = ?").bind(codeHash).first<{ id: string; status: string; expires_at: string | null }>();
  if (!license) return error("激活码无效", 403);
  if (license.status !== "unused") return error("激活码已使用或已撤销", 409);
  if (isExpired(license.expires_at)) return error("激活码已过期", 403);
  const byId = await env.DB.prepare("SELECT public_key, status FROM devices WHERE id = ?").bind(input.device_id).first<{ public_key: string; status: string }>();
  if (byId && (byId.public_key !== input.device_public_key || byId.status !== "active")) return error("设备 ID 已绑定其他密钥或已撤销", 409);
  const byKey = await env.DB.prepare("SELECT id, status FROM devices WHERE public_key = ?").bind(input.device_public_key).first<{ id: string; status: string }>();
  if (byKey && (byKey.id !== input.device_id || byKey.status !== "active")) return error("设备公钥已绑定其他设备或已撤销", 409);
  let licenseDocument: LicenseDocument;
  try { licenseDocument = await buildLicense(env, license.id, input.device_id, input.device_public_key, true); }
  catch (e) { return error(e instanceof Error ? e.message : "授权签发失败", 500); }
  await env.DB.batch([
    env.DB.prepare("INSERT OR IGNORE INTO devices (id, public_key, fingerprint) VALUES (?, ?, ?)").bind(input.device_id, input.device_public_key, input.fingerprint ?? null),
    env.DB.prepare("UPDATE licenses SET status = 'active' WHERE id = ? AND status = 'unused'").bind(license.id),
    env.DB.prepare("INSERT INTO activations (license_id, device_id) VALUES (?, ?)").bind(license.id, input.device_id)
  ]);
  return json({ license: licenseDocument });
}

async function releases(request: Request, env: Env): Promise<Response> {
  const auth = await authenticateDevice(request, env); if (auth instanceof Response) return auth;
  const grants = await env.DB.prepare("SELECT product_id, version_ranges_json, platforms_json FROM license_products WHERE license_id = ?").bind(auth.licenseId).all<{ product_id: string; version_ranges_json: string; platforms_json: string }>();
  const products = await env.DB.prepare("SELECT p.id, p.name, p.description FROM products p JOIN license_products lp ON lp.product_id = p.id WHERE lp.license_id = ? AND p.status = 'active'").bind(auth.licenseId).all<{ id: string; name: string; description: string }>();
  const rows = await env.DB.prepare("SELECT id, product_id, version, platform, sha256, signature, file_name, launch_path FROM releases WHERE status = 'active'").all<{ id: string; product_id: string; version: string; platform: string; sha256: string; signature: string | null; file_name: string; launch_path: string }>();
  const allowed = rows.results.filter((release) => grants.results.some((grant) => grant.product_id === release.product_id && JSON.parse(grant.platforms_json).includes(release.platform) && versionAllowed(release.version, JSON.parse(grant.version_ranges_json))));
  return json({ products: products.results, releases: allowed.map((release) => ({ ...release, download_url: `/api/download/${encodeURIComponent(release.id)}?license_id=${encodeURIComponent(auth.licenseId)}` })) });
}

async function refreshLicense(request: Request, env: Env): Promise<Response> {
  const auth = await authenticateDevice(request, env); if (auth instanceof Response) return auth;
  return json({ license: await buildLicense(env, auth.licenseId, auth.deviceId, auth.publicKey) });
}

async function download(request: Request, env: Env, releaseId: string): Promise<Response> {
  const auth = await authenticateDevice(request, env); if (auth instanceof Response) return auth;
  const release = await env.DB.prepare("SELECT product_id, version, platform, asset_url FROM releases WHERE id = ? AND status = 'active'").bind(releaseId).first<{ product_id: string; version: string; platform: string; asset_url: string }>();
  if (!release) return error("版本不存在", 404);
  const grant = await env.DB.prepare("SELECT version_ranges_json, platforms_json FROM license_products WHERE license_id = ? AND product_id = ?").bind(auth.licenseId, release.product_id).first<{ version_ranges_json: string; platforms_json: string }>();
  if (!grant || !JSON.parse(grant.platforms_json).includes(release.platform) || !versionAllowed(release.version, JSON.parse(grant.version_ranges_json))) return error("无权下载该版本", 403);
  if (!trustedGithubAsset(release.asset_url)) return error("版本下载地址不在允许的 GitHub 仓库范围内", 500);
  if (!env.GITHUB_TOKEN) return error("服务端未配置 GitHub Token", 500);
  let upstream = await fetch(release.asset_url, { headers: { accept: "application/octet-stream", authorization: `Bearer ${env.GITHUB_TOKEN}`, "user-agent": "WaveDAQ-License-Worker" }, redirect: "manual" });
  if (upstream.status >= 300 && upstream.status < 400) {
    const location = upstream.headers.get("location");
    if (!location) return error("GitHub 下载响应缺少跳转地址", 502);
    const target = new URL(location);
    if (target.protocol !== "https:" || !(target.hostname === "objects.githubusercontent.com" || target.hostname.endsWith(".githubusercontent.com"))) return error("GitHub 下载跳转地址不可信", 502);
    upstream = await fetch(target, { redirect: "follow" });
  }
  if (!upstream.ok || !upstream.body) return error(`上游下载失败 (${upstream.status})`, 502);
  const responseHeaders = new Headers({ "content-type": upstream.headers.get("content-type") ?? "application/octet-stream", "cache-control": "private, no-store" });
  const disposition = upstream.headers.get("content-disposition"); if (disposition) responseHeaders.set("content-disposition", disposition);
  const length = upstream.headers.get("content-length"); if (length) responseHeaders.set("content-length", length);
  return new Response(upstream.body, { status: 200, headers: responseHeaders });
}

async function admin(request: Request, env: Env, path: string): Promise<Response> {
  const denied = requireAdmin(request, env); if (denied) return denied;
  if (request.method === "GET" && path === "/products") return json({ products: (await env.DB.prepare("SELECT * FROM products ORDER BY created_at DESC").all()).results });
  if (request.method === "GET" && path === "/licenses") return json({ licenses: (await env.DB.prepare("SELECT id, status, expires_at, offline_grace_days, created_at FROM licenses ORDER BY created_at DESC LIMIT 200").all()).results });
  if (request.method === "GET" && path === "/devices") return json({ devices: (await env.DB.prepare("SELECT id, fingerprint, status, created_at, last_seen_at FROM devices ORDER BY created_at DESC LIMIT 200").all()).results });
  if (request.method === "GET" && path === "/releases") return json({ releases: (await env.DB.prepare("SELECT id, product_id, version, platform, sha256, file_name, launch_path, status, created_at FROM releases ORDER BY created_at DESC LIMIT 200").all()).results });
  if (request.method === "POST" && path === "/products") {
    const input = await body<CreateProductRequest>(request); if (!/^[a-z0-9][a-z0-9-]{1,63}$/.test(input.id) || !input.name) return error("产品字段无效");
    await env.DB.prepare("INSERT INTO products (id, name, description) VALUES (?, ?, ?)").bind(input.id, input.name, input.description ?? "").run(); return json({ id: input.id }, 201);
  }
  if (request.method === "POST" && path === "/licenses") {
    const input = await body<CreateLicenseRequest>(request); if (!input.activation_code || !input.products?.length || !input.products.every(validPermission) || !Number.isInteger(input.offline_grace_days ?? 30) || (input.offline_grace_days ?? 30) < 0 || (input.offline_grace_days ?? 30) > 3650) return error("激活码或产品权限格式无效");
    const licenseId = input.license_id ?? id("lic"); const hash = await sha256(input.activation_code.trim().toUpperCase());
    const statements = [env.DB.prepare("INSERT INTO licenses (id, code_hash, expires_at, offline_grace_days) VALUES (?, ?, ?, ?)").bind(licenseId, hash, input.expires_at ?? null, input.offline_grace_days ?? 30), ...input.products.map((product) => env.DB.prepare("INSERT INTO license_products (license_id, product_id, version_ranges_json, platforms_json, features_json) VALUES (?, ?, ?, ?, ?)").bind(licenseId, product.product_id, JSON.stringify(product.version_ranges), JSON.stringify(product.platforms), JSON.stringify(product.features ?? [])))];
    await env.DB.batch(statements); return json({ license_id: licenseId }, 201);
  }
  if (request.method === "POST" && path === "/releases") {
    const input = await body<CreateReleaseRequest>(request); if (!input.id || !input.product_id || !/^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$/.test(input.version) || !PLATFORMS.has(input.platform) || !trustedGithubAsset(input.asset_url) || !/^[a-fA-F0-9]{64}$/.test(input.sha256) || !/^[^/\\]{1,180}$/.test(input.file_name) || !input.launch_path || input.launch_path.length > 500) return error("版本字段、文件名、启动路径或 GitHub Asset API 地址无效");
    await env.DB.prepare("INSERT INTO releases (id, product_id, version, platform, asset_url, sha256, file_name, launch_path, signature) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)").bind(input.id, input.product_id, input.version, input.platform, input.asset_url, input.sha256, input.file_name, input.launch_path, input.signature ?? null).run(); return json({ id: input.id }, 201);
  }
  const revokeLicense = path.match(/^\/licenses\/([^/]+)\/revoke$/); if (request.method === "POST" && revokeLicense) { await env.DB.prepare("UPDATE licenses SET status = 'revoked' WHERE id = ?").bind(revokeLicense[1]).run(); return json({ status: "revoked", license_id: revokeLicense[1] }); }
  const revokeDevice = path.match(/^\/devices\/([^/]+)\/revoke$/); if (request.method === "POST" && revokeDevice) { await env.DB.prepare("UPDATE devices SET status = 'revoked' WHERE id = ?").bind(revokeDevice[1]).run(); return json({ status: "revoked", device_id: revokeDevice[1] }); }
  return error("管理接口不存在", 404);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/api/activate" && request.method === "POST") return await activate(request, env);
      if (url.pathname === "/api/releases" && request.method === "GET") return await releases(request, env);
      if (url.pathname === "/api/license/refresh" && request.method === "POST") return await refreshLicense(request, env);
      const releaseDownload = url.pathname.match(/^\/api\/download\/([^/]+)$/); if (releaseDownload && request.method === "GET") return await download(request, env, decodeURIComponent(releaseDownload[1]));
      if (url.pathname.startsWith("/api/admin/")) return await admin(request, env, url.pathname.replace("/api/admin", ""));
      return error("Not Found", 404);
    } catch (e) {
      console.error(e); return error("服务器处理请求失败", 500);
    }
  }
};
