/**
 * Tiny helper to fetch the list of platforms for filter UI components.
 *
 * Lives in `lib/` so server pages can import it without going through a
 * server action.
 */

import "server-only";

import prisma from "@/lib/prisma";

export type PlatformOption = { value: string; label: string };

export async function listPlatformOptions(): Promise<PlatformOption[]> {
  const rows = await prisma.platformSettings.findMany({
    orderBy: { platform: "asc" },
    select: { platform: true, displayName: true },
  });
  return rows.map((r) => ({ value: r.platform, label: r.displayName }));
}
