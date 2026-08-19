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

export function requireAdmin(request: Request, env: { ADMIN_TOKEN?: string }): Response | null {
  if (!env.ADMIN_TOKEN || request.headers.get("authorization") !== `Bearer ${env.ADMIN_TOKEN}`) {
    return error("管理员认证失败", 401);
  }
  return null;
}
