import { error, body, json, requireAdmin, createAdminSession, sessionCookie, clearSessionCookie } from "./http";
import { decryptActivationCode, encryptActivationCode, sha256, signLicense, verifyEd25519 } from "./crypto";
import { resolveGithubRelease, trustedGithubAsset } from "./releases";
import type { GithubRelease, ResolvedRelease } from "./releases";
import type { Env, LicenseDocument } from "./types";

interface ActivateRequest { activation_code: string; device_id: string; device_public_key: string; fingerprint?: string; }
interface CreateLicenseRequest { license_id?: string; name: string; activation_code: string; product_ids?: string[]; product_id?: string; term?: string; expires_at?: string | null; }
interface CreateProductRequest { product_id: string; name: string; github_repository_url: string; description?: string; }
interface UpdateLicenseRequest { term: string; expires_at?: string | null; }
interface UpdateProductRequest { github_repository_url: string; description?: string; }
interface DeviceAuth { licenseId: string; deviceId: string; publicKey: string; }

interface AdminLoginRequest { password: string; }

function id(prefix: string): string { return `${prefix}_${crypto.randomUUID().replaceAll("-", "")}`; }
function isExpired(value: string | null): boolean {
  if (value === null) return false;
  const timestamp = Date.parse(value);
  return !Number.isFinite(timestamp) || timestamp <= Date.now();
}
async function fetchLatestGithubRelease(env: Env, repository: string): Promise<GithubRelease> {
  if (!env.GITHUB_TOKEN) throw new Error("服务端未配置 GitHub Token");
  const response = await fetch(`https://api.github.com/repos/${repository}/releases/latest`, { headers: { accept: "application/vnd.github+json", "x-github-api-version": "2022-11-28", authorization: `Bearer ${env.GITHUB_TOKEN}`, "user-agent": "WaveDAQ-License-Worker" } });
  if (!response.ok) throw new Error(`无法读取 GitHub 最新版本 (${response.status})`);
  return await response.json() as GithubRelease;
}

function parseGithubRepository(value: string): string | null {
  try {
    const url = new URL(value.trim().replace(/\/$/, ""));
    if (url.protocol !== "https:" || url.hostname !== "github.com") return null;
    const parts = url.pathname.split("/").filter(Boolean).map((part, index) => index === 1 ? part.replace(/\.git$/, "") : part);
    if (parts.length !== 2 || !/^[A-Za-z0-9_.-]+$/.test(parts[0]) || !/^[A-Za-z0-9_.-]+$/.test(parts[1])) return null;
    return `${parts[0]}/${parts[1]}`;
  } catch { return null; }
}

async function buildLicense(env: Env, licenseId: string, deviceId: string, publicKey: string, allowUnused = false): Promise<LicenseDocument> {
  const statuses = allowUnused ? "('active', 'unused')" : "('active')";
  const license = await env.DB.prepare(`SELECT id, expires_at FROM licenses WHERE id = ? AND is_frozen = 0 AND status IN ${statuses}`).bind(licenseId).first<{ id: string; expires_at: string | null }>();
  if (!license || isExpired(license.expires_at)) throw new Error("授权不存在、已失效或已过期");
  const rows = await env.DB.prepare("SELECT product_id FROM license_products WHERE license_id = ?").bind(licenseId).all<{ product_id: string }>();
  const products = rows.results.map((row) => ({ product_id: row.product_id, platforms: ["windows-x64", "macos-arm64", "macos-x64"] }));
  if (!env.LICENSE_SIGNING_PRIVATE_KEY) throw new Error("服务端未配置签名私钥");
  const unsigned: Omit<LicenseDocument, "signature"> = { schema_version: "1", license_id: license.id, device_id: deviceId, device_public_key: publicKey, issued_at: new Date().toISOString(), expires_at: license.expires_at, products };
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
  const row = await env.DB.prepare("SELECT d.public_key, l.expires_at FROM activations a JOIN licenses l ON l.id = a.license_id JOIN devices d ON d.id = a.device_id WHERE a.license_id = ? AND a.device_id = ? AND l.status = 'active' AND l.is_frozen = 0 AND d.status = 'active'").bind(licenseId, deviceId).first<{ public_key: string; expires_at: string | null }>();
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
  if (!/^[A-Z2-9]{5}(?:-[A-Z2-9]{5}){3}$/.test(input.activation_code?.trim().toUpperCase() ?? "") || !/^dev_[a-f0-9]{32}$/.test(input.device_id) || !/^[A-Za-z0-9_-]{43}$/.test(input.device_public_key) || (input.fingerprint !== undefined && (typeof input.fingerprint !== "string" || input.fingerprint.length > 512))) return error("激活参数格式无效");
  const codeHash = await sha256(input.activation_code.trim().toUpperCase());
  const license = await env.DB.prepare("SELECT id, status, is_frozen, expires_at FROM licenses WHERE code_hash = ?").bind(codeHash).first<{ id: string; status: string; is_frozen: number; expires_at: string | null }>();
  if (!license) return error("激活码无效", 403);
  if (license.is_frozen) return error("授权已冻结", 409);
  if (license.status !== "unused") return error("激活码已使用或已撤销", 409);
  if (isExpired(license.expires_at)) return error("激活码已过期", 403);
  const byId = await env.DB.prepare("SELECT public_key, status FROM devices WHERE id = ?").bind(input.device_id).first<{ public_key: string; status: string }>();
  if (byId && (byId.public_key !== input.device_public_key || byId.status !== "active")) return error("设备 ID 已绑定其他密钥或已撤销", 409);
  const byKey = await env.DB.prepare("SELECT id, status FROM devices WHERE public_key = ?").bind(input.device_public_key).first<{ id: string; status: string }>();
  if (byKey && (byKey.id !== input.device_id || byKey.status !== "active")) return error("设备公钥已绑定其他设备或已撤销", 409);
  let licenseDocument: LicenseDocument;
  try { licenseDocument = await buildLicense(env, license.id, input.device_id, input.device_public_key, true); }
  catch (e) { return error(e instanceof Error ? e.message : "授权签发失败", 500); }
  try {
    await env.DB.batch([
      env.DB.prepare("INSERT OR IGNORE INTO devices (id, public_key, fingerprint) VALUES (?, ?, ?)").bind(input.device_id, input.device_public_key, input.fingerprint ?? null),
      env.DB.prepare("UPDATE licenses SET status = 'active' WHERE id = ? AND status = 'unused'").bind(license.id),
      env.DB.prepare("INSERT INTO activations (license_id, device_id) VALUES (?, ?)").bind(license.id, input.device_id)
    ]);
  } catch {
    return error("激活码已被其他设备使用，请刷新后重试", 409);
  }
  return json({ license: licenseDocument });
}

async function releases(request: Request, env: Env): Promise<Response> {
  const auth = await authenticateDevice(request, env); if (auth instanceof Response) return auth;
  const grants = await env.DB.prepare("SELECT product_id FROM license_products WHERE license_id = ?").bind(auth.licenseId).all<{ product_id: string }>();
  const products = await env.DB.prepare("SELECT p.id, p.name, p.description, p.github_repository FROM products p JOIN license_products lp ON lp.product_id = p.id WHERE lp.license_id = ? AND p.status = 'active' AND p.is_frozen = 0").bind(auth.licenseId).all<{ id: string; name: string; description: string; github_repository: string }>();
  const platforms = ["windows-x64", "macos-arm64", "macos-x64"];
  const latestByProduct = new Map<string, GithubRelease>();
  await Promise.all(products.results.map(async (product) => { latestByProduct.set(product.id, await fetchLatestGithubRelease(env, product.github_repository)); }));
  const allowed = products.results.flatMap((product) => platforms.map((platform) => {
    const grant = grants.results.find((item) => item.product_id === product.id);
    if (!grant) return null;
    const release = resolveGithubRelease(product.github_repository, product.id, latestByProduct.get(product.id)!, platform);
    if (!release) return null;
    return { ...release, download_url: `/api/download/${encodeURIComponent(release.id)}?license_id=${encodeURIComponent(auth.licenseId)}&product_id=${encodeURIComponent(release.product_id)}&platform=${encodeURIComponent(release.platform)}` };
  })).filter((release): release is ResolvedRelease & { download_url: string } => release !== null);
  return json({ products: products.results, releases: allowed });
}

async function refreshLicense(request: Request, env: Env): Promise<Response> {
  const auth = await authenticateDevice(request, env); if (auth instanceof Response) return auth;
  return json({ license: await buildLicense(env, auth.licenseId, auth.deviceId, auth.publicKey) });
}

async function download(request: Request, env: Env, releaseId: string): Promise<Response> {
  const auth = await authenticateDevice(request, env); if (auth instanceof Response) return auth;
  const url = new URL(request.url);
  const productId = url.searchParams.get("product_id") ?? "";
  const platform = url.searchParams.get("platform") ?? "";
  if (!productId || !["windows-x64", "macos-arm64", "macos-x64"].includes(platform)) return error("下载参数无效", 400);
  const product = await env.DB.prepare("SELECT id, github_repository FROM products WHERE id = ? AND status = 'active' AND is_frozen = 0").bind(productId).first<{ id: string; github_repository: string }>();
  if (!product) return error("产品不存在或已禁用", 404);
  const grant = await env.DB.prepare("SELECT 1 AS allowed FROM license_products WHERE license_id = ? AND product_id = ?").bind(auth.licenseId, productId).first<{ allowed: number }>();
  if (!grant) return error("无权下载该产品", 403);
  let release: ResolvedRelease | null;
  try {
    release = resolveGithubRelease(product.github_repository, productId, await fetchLatestGithubRelease(env, product.github_repository), platform);
  } catch (e) {
    return error(e instanceof Error ? e.message : "无法读取产品最新版本", 502);
  }
  if (!release || release.id !== releaseId) return error("版本已更新，请重新在线检查更新", 404);
  if (!trustedGithubAsset(release.asset_url, product.github_repository)) return error("版本下载地址不在允许的 GitHub 仓库范围内", 500);
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

async function verifyAdminPassword(password: string, encoded: string): Promise<boolean> {
  const normalized = encoded.trim().replace(/^(\"|')(.*)\1$/, "$2");
  const delimiter = normalized.includes(":") ? ":" : "$";
  const parts = normalized.split(delimiter);
  if (parts.length !== 4 || parts[0] !== "pbkdf2-sha256") return false;
  const iterations = Number(parts[1]);
  if (!Number.isInteger(iterations) || iterations < 100_000 || iterations > 2_000_000) return false;
  try {
    const salt = base64urlToBytes(parts[2]);
    const expected = base64urlToBytes(parts[3]);
    const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(password), { name: "PBKDF2" }, false, ["deriveBits"]);
    const actual = new Uint8Array(await crypto.subtle.deriveBits({ name: "PBKDF2", salt, iterations, hash: "SHA-256" }, key, expected.length * 8));
    if (actual.length !== expected.length) return false;
    let difference = 0;
    for (let index = 0; index < actual.length; index += 1) difference |= actual[index] ^ expected[index];
    return difference === 0;
  } catch { throw new Error("管理员密码校验器配置无效"); }
}

function base64urlToBytes(value: string): Uint8Array {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - value.length % 4) % 4);
  return Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
}

async function adminLogin(request: Request, env: Env): Promise<Response> {
  if (!env.ADMIN_TOKEN || !env.ADMIN_PASSWORD_HASH) return error("服务端未配置管理员登录", 503);
  const clientAddress = request.headers.get("cf-connecting-ip") ?? "unknown";
  const clientHash = await sha256(`${env.ADMIN_TOKEN}\0${clientAddress}`);
  const now = Date.now();
  const attempt = await env.DB.prepare("SELECT failures, first_failed_at, blocked_until FROM admin_login_attempts WHERE client_hash = ?").bind(clientHash).first<{ failures: number; first_failed_at: string; blocked_until: string | null }>();
  if (attempt?.blocked_until && Date.parse(attempt.blocked_until) > now) {
    const retryAfter = Math.max(1, Math.ceil((Date.parse(attempt.blocked_until) - now) / 1000));
    return new Response(JSON.stringify({ error: "登录尝试过多，请稍后再试" }), { status: 429, headers: { "content-type": "application/json", "cache-control": "no-store", "retry-after": String(retryAfter) } });
  }
  const input = await body<AdminLoginRequest>(request);
  let passwordValid = false;
  try { passwordValid = !!input.password && await verifyAdminPassword(input.password, env.ADMIN_PASSWORD_HASH); }
  catch { return error("服务端密码校验配置错误", 503); }
  if (!passwordValid) {
    const windowStarted = attempt ? Date.parse(attempt.first_failed_at) : Number.NaN;
    const withinWindow = Number.isFinite(windowStarted) && now - windowStarted < 15 * 60 * 1000;
    const failures = withinWindow ? attempt!.failures + 1 : 1;
    const firstFailedAt = withinWindow ? attempt!.first_failed_at : new Date(now).toISOString();
    const blockedUntil = failures >= 10 ? new Date(now + 15 * 60 * 1000).toISOString() : null;
    await env.DB.prepare("INSERT INTO admin_login_attempts (client_hash, failures, first_failed_at, last_failed_at, blocked_until) VALUES (?, ?, ?, ?, ?) ON CONFLICT(client_hash) DO UPDATE SET failures = excluded.failures, first_failed_at = excluded.first_failed_at, last_failed_at = excluded.last_failed_at, blocked_until = excluded.blocked_until").bind(clientHash, failures, firstFailedAt, new Date(now).toISOString(), blockedUntil).run();
    return error("密码错误", 401);
  }
  await env.DB.prepare("DELETE FROM admin_login_attempts WHERE client_hash = ?").bind(clientHash).run();
  return new Response(JSON.stringify({ ok: true }), { headers: { "content-type": "application/json", "set-cookie": sessionCookie(await createAdminSession(env.ADMIN_TOKEN)), "cache-control": "no-store" } });
}

async function admin(request: Request, env: Env, path: string): Promise<Response> {
  const denied = await requireAdmin(request, env); if (denied) return denied;
  if (request.method === "GET" && path === "/products") return json({ products: (await env.DB.prepare("SELECT id, name, description, github_repository, status, is_frozen, created_at FROM products ORDER BY created_at DESC").all()).results });
  if (request.method === "POST" && path === "/products") {
    const input = await body<CreateProductRequest>(request);
    const productId = input.product_id?.trim(); const name = input.name?.trim(); const repository = parseGithubRepository(input.github_repository_url ?? "");
    if (!productId || !/^[a-z0-9][a-z0-9._-]{2,63}$/.test(productId) || !name || name.length > 100 || !repository || (input.description ?? "").length > 500) return error("产品 ID、名称或 GitHub 仓库链接无效");
    try { await env.DB.prepare("INSERT INTO products (id, name, description, github_repository) VALUES (?, ?, ?, ?)").bind(productId, name, input.description?.trim() ?? "", repository).run(); }
    catch { return error("产品创建失败", 409); }
    return json({ product_id: productId }, 201);
  }
  const productIdMatch = path.match(/^\/products\/([^/]+)$/);
  if (request.method === "PATCH" && productIdMatch) {
    const productId = decodeURIComponent(productIdMatch[1]);
    const input = await body<UpdateProductRequest>(request);
    const repository = parseGithubRepository(input.github_repository_url ?? "");
    if (!repository || (input.description ?? "").length > 500) return error("GitHub 仓库链接或说明无效");
    const result = await env.DB.prepare("UPDATE products SET github_repository = ?, description = ? WHERE id = ? AND status != 'disabled'").bind(repository, input.description?.trim() ?? "", productId).run();
    if (!result.meta.changes) return error("产品不存在、已删除或不可修改", 404);
    return json({ product_id: productId });
  }
  if (request.method === "DELETE" && productIdMatch) {
    const productId = decodeURIComponent(productIdMatch[1]);
    const references = await env.DB.prepare("SELECT COUNT(*) AS total FROM license_products WHERE product_id = ?").bind(productId).first<{ total: number }>();
    if (references && references.total > 0) {
      const archived = await env.DB.prepare("UPDATE products SET status = 'disabled', is_frozen = 0 WHERE id = ?").bind(productId).run();
      if (!archived.meta.changes) return error("产品不存在", 404);
      return json({ product_id: productId, deleted: true, historical: true });
    }
    const result = await env.DB.prepare("DELETE FROM products WHERE id = ?").bind(productId).run();
    if (!result.meta.changes) return error("产品不存在", 404);
    return json({ product_id: productId, deleted: true });
  }
  if (request.method === "GET" && path === "/licenses") return json({ licenses: (await env.DB.prepare("SELECT l.id, l.name, l.status, l.is_frozen, l.term, l.expires_at, l.created_at, CASE WHEN l.code_ciphertext IS NULL THEN 0 ELSE 1 END AS has_code, GROUP_CONCAT(DISTINCT p.name) AS product_names, MAX(a.activated_at) AS activated_at, GROUP_CONCAT(DISTINCT a.device_id) AS device_ids, MIN(d.created_at) AS first_bound_at FROM licenses l LEFT JOIN license_products lp ON lp.license_id = l.id LEFT JOIN products p ON p.id = lp.product_id LEFT JOIN activations a ON a.license_id = l.id LEFT JOIN devices d ON d.id = a.device_id GROUP BY l.id ORDER BY l.created_at DESC LIMIT 200").all()).results });
  if (request.method === "GET" && path === "/devices") return json({ devices: (await env.DB.prepare("SELECT id, fingerprint, status, created_at, last_seen_at FROM devices ORDER BY created_at DESC LIMIT 200").all()).results });
  if (request.method === "POST" && path === "/licenses") {
    const input = await body<CreateLicenseRequest>(request);
    const name = input.name?.trim();
    const activationCode = input.activation_code?.trim().toUpperCase();
    const expiresAt = input.expires_at?.trim() || null;
    const productIds = [...new Set(input.product_ids?.length ? input.product_ids : (input.product_id ? [input.product_id] : []))];
    if (!name || name.length > 120 || !/^[A-Z2-9]{5}(?:-[A-Z2-9]{5}){3}$/.test(activationCode ?? "") || productIds.length === 0 || productIds.length > 20) return error("激活码名称、格式或授权产品无效");
    if (expiresAt && (!Number.isFinite(Date.parse(expiresAt)) || Date.parse(expiresAt) <= Date.now())) return error("过期时间必须是有效的未来时间");
    const productRows = await env.DB.prepare(`SELECT id FROM products WHERE status = 'active' AND is_frozen = 0 AND id IN (${productIds.map(() => "?").join(",")})`).bind(...productIds).all<{ id: string }>();
    if (productRows.results.length !== productIds.length) return error("授权产品不存在或已禁用");
    if (!env.ADMIN_TOKEN) return error("服务端未配置管理员密钥", 503);
    const licenseId = input.license_id ?? id("lic"); const hash = await sha256(activationCode!); const encryptedCode = await encryptActivationCode(activationCode!, env.ADMIN_TOKEN);
    const term = input.term?.trim() || (expiresAt ? "自定义" : "永久授权");
    if (term !== "永久授权" && term !== "自定义") return error("授权期限只能是永久授权或自定义");
    if (term === "永久授权" && expiresAt) return error("永久授权不能设置过期时间");
    if (term === "自定义" && !expiresAt) return error("自定义授权必须设置过期时间");
    const statements = [env.DB.prepare("INSERT INTO licenses (id, name, code_hash, code_ciphertext, expires_at, term) VALUES (?, ?, ?, ?, ?, ?)").bind(licenseId, name, hash, encryptedCode, expiresAt, term), ...productIds.map((productId) => env.DB.prepare("INSERT INTO license_products (license_id, product_id) VALUES (?, ?)").bind(licenseId, productId))];
    try {
      await env.DB.batch(statements);
    } catch {
      return error("激活码或授权 ID 已存在", 409);
    }
    return json({ license_id: licenseId }, 201);
  }
  const licenseCode = path.match(/^\/licenses\/([^/]+)\/code$/);
  if (request.method === "GET" && licenseCode) {
    if (!env.ADMIN_TOKEN) return error("服务端未配置管理员密钥", 503);
    const licenseId = decodeURIComponent(licenseCode[1]);
    const row = await env.DB.prepare("SELECT code_ciphertext FROM licenses WHERE id = ?").bind(licenseId).first<{ code_ciphertext: string | null }>();
    if (!row) return error("授权不存在", 404);
    if (!row.code_ciphertext) return error("该授权创建于启用查看功能之前，未保存可恢复的激活码", 404);
    try { return json({ license_id: licenseId, activation_code: await decryptActivationCode(row.code_ciphertext, env.ADMIN_TOKEN) }); }
    catch { return error("激活码解密失败，请检查管理员密钥配置", 503); }
  }
  const licenseIdMatch = path.match(/^\/licenses\/([^/]+)$/);
  if (request.method === "PATCH" && licenseIdMatch) {
    const licenseId = decodeURIComponent(licenseIdMatch[1]);
    const input = await body<UpdateLicenseRequest>(request);
    const term = input.term?.trim();
    const expiresAt = input.expires_at?.trim() || null;
    if (term !== "永久授权" && term !== "自定义") return error("授权期限只能是永久授权或自定义");
    if (term === "永久授权" && expiresAt) return error("永久授权不能设置过期时间");
    if (term === "自定义" && (!expiresAt || !Number.isFinite(Date.parse(expiresAt)) || Date.parse(expiresAt) <= Date.now())) return error("自定义授权必须设置有效的未来过期时间");
    const result = await env.DB.prepare("UPDATE licenses SET term = ?, expires_at = ? WHERE id = ? AND status != 'revoked'").bind(term, expiresAt, licenseId).run();
    if (!result.meta.changes) return error("授权不存在或已撤销", 404);
    return json({ license_id: licenseId });
  }
  const revokeLicense = path.match(/^\/licenses\/([^/]+)\/revoke$/); if (request.method === "POST" && revokeLicense) { const result = await env.DB.prepare("UPDATE licenses SET status = 'revoked', is_frozen = 0 WHERE id = ? AND status != 'revoked'").bind(revokeLicense[1]).run(); if (!result.meta.changes) return error("授权不存在或已经撤销", 404); return json({ status: "revoked", license_id: revokeLicense[1] }); }
  const productFreeze = path.match(/^\/products\/([^/]+)\/(freeze|unfreeze)$/);
  if (request.method === "POST" && productFreeze) {
    const productId = decodeURIComponent(productFreeze[1]); const frozen = productFreeze[2] === "freeze" ? 1 : 0;
    const result = await env.DB.prepare("UPDATE products SET is_frozen = ? WHERE id = ? AND status != 'disabled'").bind(frozen, productId).run();
    if (!result.meta.changes) return error("产品不存在或已删除", 404);
    return json({ status: frozen ? "frozen" : "active", product_id: productId });
  }
  const licenseFreeze = path.match(/^\/licenses\/([^/]+)\/(freeze|unfreeze)$/);
  if (request.method === "POST" && licenseFreeze) {
    const licenseId = decodeURIComponent(licenseFreeze[1]); const frozen = licenseFreeze[2] === "freeze" ? 1 : 0;
    const result = await env.DB.prepare("UPDATE licenses SET is_frozen = ? WHERE id = ? AND status != 'revoked'").bind(frozen, licenseId).run();
    if (!result.meta.changes) return error("授权不存在或已撤销", 404);
    return json({ status: frozen ? "frozen" : "active", license_id: licenseId });
  }
  const unbindDevice = path.match(/^\/devices\/([^/]+)\/unbind$/);
  if (request.method === "POST" && unbindDevice) {
    const deviceId = decodeURIComponent(unbindDevice[1]);
    await env.DB.batch([
      env.DB.prepare("UPDATE licenses SET status = 'unused' WHERE status = 'active' AND id IN (SELECT license_id FROM activations WHERE device_id = ?)").bind(deviceId),
      env.DB.prepare("DELETE FROM request_nonces WHERE device_id = ?").bind(deviceId),
      env.DB.prepare("DELETE FROM activations WHERE device_id = ? AND license_id IN (SELECT id FROM licenses WHERE status != 'revoked')").bind(deviceId),
      env.DB.prepare("DELETE FROM devices WHERE id = ? AND NOT EXISTS (SELECT 1 FROM activations WHERE device_id = ?)").bind(deviceId, deviceId)
    ]);
    return json({ status: "unbound", device_id: deviceId });
  }
  return error("管理接口不存在", 404);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/api/activate" && request.method === "POST") return await activate(request, env);
      if (url.pathname === "/api/releases" && request.method === "GET") return await releases(request, env);
      if (url.pathname === "/api/license/refresh" && request.method === "POST") return await refreshLicense(request, env);
      if (url.pathname === "/api/admin/login" && request.method === "POST") return await adminLogin(request, env);
      if (url.pathname === "/api/admin/logout" && request.method === "POST") return new Response(JSON.stringify({ ok: true }), { headers: { "content-type": "application/json", "set-cookie": clearSessionCookie(), "cache-control": "no-store" } });
      const releaseDownload = url.pathname.match(/^\/api\/download\/([^/]+)$/); if (releaseDownload && request.method === "GET") return await download(request, env, decodeURIComponent(releaseDownload[1]));
      if (url.pathname.startsWith("/api/admin/")) return await admin(request, env, url.pathname.replace("/api/admin", ""));
      return error("Not Found", 404);
    } catch (e) {
      if (e instanceof SyntaxError) return error("请求 JSON 格式无效", 400);
      console.error(e); return error("服务器处理请求失败", 500);
    }
  }
};
