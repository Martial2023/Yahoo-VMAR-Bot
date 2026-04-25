import "server-only";

const BASE = process.env.BACKEND_API_URL?.replace(/\/$/, "") ?? "";
const TOKEN = process.env.BACKEND_API_TOKEN ?? "";

type Json = Record<string, unknown>;

class BackendError extends Error {
  constructor(public status: number, public body: string) {
    super(`Backend ${status}: ${body}`);
  }
}

async function call<T = Json>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  if (!BASE) throw new Error("BACKEND_API_URL is not configured");
  if (!TOKEN) throw new Error("BACKEND_API_TOKEN is not configured");

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${TOKEN}`,
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });

  const text = await res.text();
  if (!res.ok) throw new BackendError(res.status, text);
  return text ? (JSON.parse(text) as T) : ({} as T);
}

export type BackendStatus = {
  bot_enabled: boolean;
  mode: string;
  ticker: string;
  trigger_pending: boolean;
  shutdown_requested: boolean;
};

export async function getBackendHealth(): Promise<{ status: string } | null> {
  if (!BASE) return null;
  try {
    const res = await fetch(`${BASE}/health`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as { status: string };
  } catch {
    return null;
  }
}

export async function getBackendStatus(): Promise<BackendStatus | null> {
  try {
    return await call<BackendStatus>("/status");
  } catch (e) {
    console.warn("[backend-api] getBackendStatus failed:", e);
    return null;
  }
}

export async function triggerCycle(): Promise<{ ok: boolean; detail?: string }> {
  return call("/trigger-cycle", { method: "POST" });
}

export async function reloadConfig(): Promise<{ ok: boolean; detail?: string }> {
  return call("/reload-config", { method: "POST" });
}

export async function stopBackend(): Promise<{ ok: boolean; detail?: string }> {
  return call("/stop", { method: "POST" });
}
