export function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" }
  });
}

export function error(message: string, status = 400): Response {
  return json({ error: message }, status);
}

export async function body<T>(request: Request): Promise<T> {
  return await request.json() as T;
}

const SESSION_TTL_SECONDS = 8 * 60 * 60;

function constantTimeEqual(left: Uint8Array, right: Uint8Array): boolean {
  if (left.length !== right.length) return false;
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) difference |= left[index] ^ right[index];
  return difference === 0;
}

function bytesToBase64url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64urlToBytes(value: string): Uint8Array {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - value.length % 4) % 4);
  return Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
}

async function sessionSignature(value: string, secret: string): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(value)));
}

export async function createAdminSession(secret: string): Promise<string> {
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const value = `v1.${timestamp}`;
  return `${value}.${bytesToBase64url(await sessionSignature(value, secret))}`;
}

function getCookie(request: Request, name: string): string | null {
  const cookies = request.headers.get("cookie")?.split(";") ?? [];
  const item = cookies.find((cookie) => cookie.trim().startsWith(`${name}=`));
  return item ? item.trim().slice(name.length + 1) : null;
}

export async function requireAdmin(request: Request, env: { ADMIN_TOKEN?: string }): Promise<Response | null> {
  const authorization = request.headers.get("authorization") ?? "";
  const bearer = authorization.startsWith("Bearer ") ? authorization.slice(7) : "";
  let bearerValid = false;
  if (env.ADMIN_TOKEN && bearer) {
    const [actual, expected] = await Promise.all([
      sessionSignature("wavedaq-admin-bearer", bearer),
      sessionSignature("wavedaq-admin-bearer", env.ADMIN_TOKEN)
    ]);
    bearerValid = constantTimeEqual(actual, expected);
  }
  const session = getCookie(request, "wavedaq_admin_session");
  let sessionValid = false;
  if (env.ADMIN_TOKEN && session) {
    const parts = session.split(".");
    if (parts.length === 3 && parts[0] === "v1") {
      const timestamp = Number(parts[1]);
      if (Number.isInteger(timestamp) && Math.abs(Math.floor(Date.now() / 1000) - timestamp) <= SESSION_TTL_SECONDS) {
        try {
          sessionValid = constantTimeEqual(base64urlToBytes(parts[2]), await sessionSignature(`${parts[0]}.${parts[1]}`, env.ADMIN_TOKEN));
        } catch { sessionValid = false; }
      }
    }
  }
  if (!bearerValid && !sessionValid) {
    return error("管理员认证失败", 401);
  }
  return null;
}

export function sessionCookie(value: string): string {
  return `wavedaq_admin_session=${value}; Max-Age=${SESSION_TTL_SECONDS}; Path=/; HttpOnly; Secure; SameSite=Strict`;
}

export function clearSessionCookie(): string {
  return "wavedaq_admin_session=; Max-Age=0; Path=/; HttpOnly; Secure; SameSite=Strict";
}
