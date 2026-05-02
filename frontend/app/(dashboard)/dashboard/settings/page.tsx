import Link from "next/link";
import { notFound } from "next/navigation";
import { CheckIcon, XIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import prisma from "@/lib/prisma";

import { type ImapConfig } from "@/app/(actions)/actions";
import SettingsForm from "./_components/SettingsForm";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const [global, platforms] = await Promise.all([
    prisma.botSettings.findUnique({ where: { id: 1 } }),
    prisma.platformSettings.findMany({ orderBy: { platform: "asc" } }),
  ]);
  if (!global) notFound();

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Settings</h1>
          <p className="text-sm text-muted-foreground">
            Global preferences and per-platform configuration. Changes are picked
            up by the worker on the next cycle (or immediately via reload).
          </p>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-lg font-semibold">Platforms</h2>
          <p className="text-sm text-muted-foreground">
            Each platform has its own quotas, schedule, prompts, and credentials.
          </p>
        </div>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {platforms.length === 0 && (
            <Card>
              <CardHeader>
                <CardTitle>No platforms configured</CardTitle>
                <CardDescription>
                  Run <code>pnpm prisma db seed</code> to create the default rows.
                </CardDescription>
              </CardHeader>
            </Card>
          )}
          {platforms.map((p) => (
            <Card key={p.platform} className="flex flex-col">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{p.displayName}</CardTitle>
                  <Badge
                    variant={p.enabled ? "default" : "secondary"}
                    className={p.enabled ? "bg-green-500" : ""}
                  >
                    {p.enabled ? <CheckIcon className="size-3 mr-1" /> : <XIcon className="size-3 mr-1" />}
                    {p.enabled ? "enabled" : "disabled"}
                  </Badge>
                </div>
                <CardDescription className="text-xs">
                  {p.platform} · mode: <strong>{p.mode}</strong>
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm flex-1">
                <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                  <div>
                    <span className="block">Replies/day</span>
                    <span className="text-foreground">{p.maxRepliesPerDay}</span>
                  </div>
                  <div>
                    <span className="block">Posts/day</span>
                    <span className="text-foreground">{p.maxPostsPerDay}</span>
                  </div>
                  <div className="col-span-2">
                    <span className="block">Slots</span>
                    <span className="text-foreground font-mono">
                      {p.scheduleSlots.length > 0 ? p.scheduleSlots.join(", ") : "—"}
                    </span>
                  </div>
                </div>
                <Button asChild variant="outline" className="w-full mt-auto">
                  <Link href={`/dashboard/settings/${p.platform}`}>Configure</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-lg font-semibold">Global settings</h2>
          <p className="text-sm text-muted-foreground">
            Master kill switch, AI model, default prompts, alert recipients —
            shared across all platforms.
          </p>
        </div>
        <SettingsForm
          initial={{
            botEnabled: global.botEnabled,
            mode: global.mode as "reply" | "post" | "both",
            ticker: global.ticker,
            checkIntervalMin: global.checkIntervalMin,
            checkIntervalMax: global.checkIntervalMax,
            maxRepliesPerHour: global.maxRepliesPerHour,
            maxPostsPerDay: global.maxPostsPerDay,
            aiModel: global.aiModel,
            aiTemperature: global.aiTemperature,
            replyPrompt: global.replyPrompt,
            postPrompt: global.postPrompt,
            alertEmails: global.alertEmails,
            imapConfig: (global.imapConfig as ImapConfig | null) ?? null,
          }}
        />
      </section>
    </div>
  );
}
