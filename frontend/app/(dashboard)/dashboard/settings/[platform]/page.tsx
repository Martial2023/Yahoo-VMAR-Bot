import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeftIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import prisma from "@/lib/prisma";

import PlatformSettingsForm from "./_components/PlatformSettingsForm";

export const dynamic = "force-dynamic";

type Params = Promise<{ platform: string }>;

export default async function PlatformSettingsPage({
  params,
}: {
  params: Params;
}) {
  const { platform } = await params;
  const row = await prisma.platformSettings.findUnique({ where: { platform } });
  if (!row) notFound();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Button asChild variant="ghost" size="sm" className="mb-2">
            <Link href="/dashboard/settings">
              <ChevronLeftIcon className="size-4" /> Back to settings
            </Link>
          </Button>
          <h1 className="text-2xl font-semibold">{row.displayName}</h1>
          <p className="text-sm text-muted-foreground">
            Per-platform configuration · key: <code>{row.platform}</code>
          </p>
        </div>
      </div>

      <PlatformSettingsForm
        platform={row.platform}
        displayName={row.displayName}
        initial={{
          enabled: row.enabled,
          mode: row.mode as "test" | "production",
          replyEnabled: row.replyEnabled,
          postEnabled: row.postEnabled,
          ticker: row.ticker,
          maxRepliesPerDay: row.maxRepliesPerDay,
          maxPostsPerDay: row.maxPostsPerDay,
          minPostLength: row.minPostLength,
          scheduleSlots: row.scheduleSlots,
          scheduleJitterMin: row.scheduleJitterMin,
          replyPrompt: row.replyPrompt,
          postPrompt: row.postPrompt,
          credentialsJson: row.credentials
            ? JSON.stringify(row.credentials, null, 2)
            : "",
          configJson: row.config ? JSON.stringify(row.config, null, 2) : "",
        }}
      />
    </div>
  );
}
