"use server";

import { revalidatePath } from "next/cache";

import { getUser } from "@/lib/auth-session";
import { reloadConfig, triggerCycle } from "@/lib/backend-api";
import prisma from "@/lib/prisma";

async function requireUser() {
  const user = await getUser();
  if (!user) throw new Error("Unauthorized");
  return user;
}

export type SettingsInput = {
  botEnabled: boolean;
  mode: "reply" | "post" | "both";
  ticker: string;
  checkIntervalMin: number;
  checkIntervalMax: number;
  maxRepliesPerHour: number;
  maxPostsPerDay: number;
  aiModel: string;
  aiTemperature: number;
  replyPrompt: string;
  postPrompt: string;
  alertEmails: string[];
};

export async function updateBotSettings(input: SettingsInput) {
  await requireUser();

  if (input.checkIntervalMin > input.checkIntervalMax) {
    return { ok: false, error: "checkIntervalMin must be ≤ checkIntervalMax" };
  }
  if (!["reply", "post", "both"].includes(input.mode)) {
    return { ok: false, error: "Invalid mode" };
  }

  await prisma.botSettings.update({
    where: { id: 1 },
    data: input,
  });

  // Demander au backend de recharger sa config (best-effort)
  try {
    await reloadConfig();
  } catch (e) {
    console.warn("[actions] reloadConfig failed:", e);
  }

  revalidatePath("/dashboard");
  revalidatePath("/dashboard/settings");
  return { ok: true };
}

export async function runCycleNow() {
  await requireUser();
  try {
    const result = await triggerCycle();
    return { ok: true, detail: result.detail };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

export async function reloadBackendConfig() {
  await requireUser();
  try {
    const result = await reloadConfig();
    return { ok: true, detail: result.detail };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}
