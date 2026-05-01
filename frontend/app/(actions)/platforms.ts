"use server";

import { revalidatePath } from "next/cache";

import { getUser } from "@/lib/auth-session";
import { reloadConfig, triggerPlatformCycle } from "@/lib/backend-api";
import prisma from "@/lib/prisma";

async function requireUser() {
  const user = await getUser();
  if (!user) throw new Error("Unauthorized");
  return user;
}

// ----------------------------------------------------------------------------
// PlatformSettings — full update from the per-platform settings form
// ----------------------------------------------------------------------------

export type PlatformSettingsInput = {
  enabled: boolean;
  mode: "test" | "production";
  replyEnabled: boolean;
  postEnabled: boolean;
  ticker: string;
  maxRepliesPerDay: number;
  maxPostsPerDay: number;
  minPostLength: number;
  scheduleSlots: string[];
  scheduleJitterMin: number;
  replyPrompt: string | null;
  postPrompt: string | null;
  /** Stringified JSON, edited as a textarea by the operator. */
  credentialsJson: string;
  configJson: string;
};

function safeParseJson(raw: string, fallback: unknown = null): { ok: true; value: unknown } | { ok: false; error: string } {
  if (!raw.trim()) return { ok: true, value: fallback };
  try {
    return { ok: true, value: JSON.parse(raw) };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

function isValidSlot(s: string): boolean {
  return /^([01]?\d|2[0-3]):[0-5]\d$/.test(s.trim());
}

export async function updatePlatformSettings(
  platform: string,
  input: PlatformSettingsInput,
) {
  await requireUser();

  if (!["test", "production"].includes(input.mode)) {
    return { ok: false, error: "Invalid mode (expected test|production)" };
  }
  for (const slot of input.scheduleSlots) {
    if (!isValidSlot(slot)) {
      return { ok: false, error: `Invalid schedule slot: "${slot}" (HH:MM expected)` };
    }
  }

  const credentials = safeParseJson(input.credentialsJson, null);
  if (!credentials.ok) {
    return { ok: false, error: `credentials JSON invalid: ${credentials.error}` };
  }
  const config = safeParseJson(input.configJson, null);
  if (!config.ok) {
    return { ok: false, error: `config JSON invalid: ${config.error}` };
  }

  await prisma.platformSettings.update({
    where: { platform },
    data: {
      enabled: input.enabled,
      mode: input.mode,
      replyEnabled: input.replyEnabled,
      postEnabled: input.postEnabled,
      ticker: input.ticker,
      maxRepliesPerDay: input.maxRepliesPerDay,
      maxPostsPerDay: input.maxPostsPerDay,
      minPostLength: input.minPostLength,
      scheduleSlots: input.scheduleSlots,
      scheduleJitterMin: input.scheduleJitterMin,
      replyPrompt: input.replyPrompt,
      postPrompt: input.postPrompt,
      credentials: credentials.value as never,
      config: config.value as never,
    },
  });

  // Best-effort reload — the worker also reloads on the next tick anyway.
  try {
    await reloadConfig();
  } catch (e) {
    console.warn("[actions] reloadConfig failed:", e);
  }

  revalidatePath("/dashboard");
  revalidatePath("/dashboard/settings");
  revalidatePath(`/dashboard/settings/${platform}`);
  return { ok: true };
}

export async function togglePlatform(platform: string, enabled: boolean) {
  await requireUser();
  await prisma.platformSettings.update({
    where: { platform },
    data: { enabled },
  });
  try {
    await reloadConfig();
  } catch (e) {
    console.warn("[actions] reloadConfig failed:", e);
  }
  revalidatePath("/dashboard");
  revalidatePath("/dashboard/settings");
  return { ok: true };
}

// ----------------------------------------------------------------------------
// Whitelisted authors
// ----------------------------------------------------------------------------

export async function addWhitelistEntry(
  platform: string,
  authorHandle: string,
  note: string | null,
) {
  await requireUser();
  const handle = authorHandle.trim().toLowerCase();
  if (!handle) {
    return { ok: false, error: "Author handle is required" };
  }
  await prisma.whitelistedAuthor.upsert({
    where: { platform_authorHandle: { platform, authorHandle: handle } },
    update: { note },
    create: { platform, authorHandle: handle, note },
  });
  revalidatePath("/dashboard/whitelist");
  return { ok: true };
}

export async function removeWhitelistEntry(id: string) {
  await requireUser();
  let parsed: bigint;
  try {
    parsed = BigInt(id);
  } catch {
    return { ok: false, error: "Invalid id" };
  }
  await prisma.whitelistedAuthor.delete({ where: { id: parsed } });
  revalidatePath("/dashboard/whitelist");
  return { ok: true };
}

// ----------------------------------------------------------------------------
// Manual platform-scoped cycle trigger
// ----------------------------------------------------------------------------

export async function runPlatformCycle(platform: string) {
  await requireUser();
  try {
    const result = await triggerPlatformCycle(platform);
    return { ok: true, detail: result.detail };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}
