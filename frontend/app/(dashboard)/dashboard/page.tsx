import Link from "next/link";
import {
  ActivityIcon,
  CheckIcon,
  MessageSquareIcon,
  ReplyIcon,
  ShieldAlertIcon,
  XIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getBackendHealth, getBackendStatus } from "@/lib/backend-api";
import prisma from "@/lib/prisma";

import { TriggerCycleButton } from "./_components/TriggerCycleButton";

export const dynamic = "force-dynamic";

async function getOverview() {
  const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
  const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);

  const [
    settings,
    repliesToday,
    postsToday,
    repliesLastHour,
    errorsToday,
    seenComments,
    lastRun,
  ] = await Promise.all([
    prisma.botSettings.findUnique({ where: { id: 1 } }),
    prisma.botActivity.count({
      where: { type: "reply", status: "success", createdAt: { gt: oneDayAgo } },
    }),
    prisma.botActivity.count({
      where: { type: "post", status: "success", createdAt: { gt: oneDayAgo } },
    }),
    prisma.botActivity.count({
      where: { type: "reply", status: "success", createdAt: { gt: oneHourAgo } },
    }),
    prisma.botActivity.count({
      where: { status: "failed", createdAt: { gt: oneDayAgo } },
    }),
    prisma.seenComment.count(),
    prisma.botRun.findFirst({ orderBy: { startedAt: "desc" } }),
  ]);

  return {
    settings,
    repliesToday,
    postsToday,
    repliesLastHour,
    errorsToday,
    seenComments,
    lastRun,
  };
}

async function getPerPlatformOverview() {
  const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000);
  const platforms = await prisma.platformSettings.findMany({
    orderBy: { platform: "asc" },
  });

  return Promise.all(
    platforms.map(async (p) => {
      const [replies, posts, errors, lastRun] = await Promise.all([
        prisma.botActivity.count({
          where: {
            platform: p.platform,
            type: "reply",
            status: "success",
            createdAt: { gt: oneDayAgo },
          },
        }),
        prisma.botActivity.count({
          where: {
            platform: p.platform,
            type: "post",
            status: "success",
            createdAt: { gt: oneDayAgo },
          },
        }),
        prisma.botActivity.count({
          where: {
            platform: p.platform,
            status: "failed",
            createdAt: { gt: oneDayAgo },
          },
        }),
        prisma.botRun.findFirst({
          where: { platform: p.platform },
          orderBy: { startedAt: "desc" },
        }),
      ]);
      return {
        platform: p.platform,
        displayName: p.displayName,
        enabled: p.enabled,
        mode: p.mode,
        scheduleSlots: p.scheduleSlots,
        maxRepliesPerDay: p.maxRepliesPerDay,
        maxPostsPerDay: p.maxPostsPerDay,
        replies,
        posts,
        errors,
        lastRun,
      };
    }),
  );
}

export default async function DashboardPage() {
  const [data, perPlatform, status, health] = await Promise.all([
    getOverview(),
    getPerPlatformOverview(),
    getBackendStatus(),
    getBackendHealth(),
  ]);

  const { settings, repliesToday, postsToday, repliesLastHour, errorsToday, seenComments, lastRun } = data;
  const backendOnline = health !== null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Overview</h1>
          <p className="text-sm text-muted-foreground">Bot state across all platforms</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant={backendOnline ? "default" : "destructive"} className={`${backendOnline && "bg-green-500"}`}>
            Backend {backendOnline ? "online" : "offline"}
          </Badge>
          {settings?.botEnabled ? (
            <Badge variant="default">Bot enabled</Badge>
          ) : (
            <Badge variant="secondary">Bot disabled</Badge>
          )}
          <TriggerCycleButton />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Active platforms</CardDescription>
            <CardTitle className="text-2xl">
              {perPlatform.filter((p) => p.enabled).length} / {perPlatform.length}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {perPlatform.filter((p) => p.enabled).map((p) => p.displayName).join(", ") || "none"}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Replies (24h, all platforms)</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2">
              <ReplyIcon className="size-5" /> {repliesToday}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            This hour: {repliesLastHour}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Posts (24h, all platforms)</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2">
              <MessageSquareIcon className="size-5" /> {postsToday}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Comments seen: {seenComments}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Errors (24h)</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2">
              <ShieldAlertIcon className="size-5" /> {errorsToday}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            {errorsToday === 0 ? "All green" : "Needs attention"}
          </CardContent>
        </Card>
      </div>

      {/* Per-platform overview */}
      <div className="flex flex-col gap-3">
        <div>
          <h2 className="text-lg font-semibold">Per-platform overview</h2>
          <p className="text-sm text-muted-foreground">Last 24 hours</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {perPlatform.length === 0 && (
            <Card>
              <CardHeader>
                <CardTitle>No platforms</CardTitle>
                <CardDescription>
                  Run <code>pnpm prisma db seed</code> to create the default rows.
                </CardDescription>
              </CardHeader>
            </Card>
          )}
          {perPlatform.map((p) => (
            <Card key={p.platform} className="flex flex-col">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{p.displayName}</CardTitle>
                  <Badge
                    variant={p.enabled ? "default" : "secondary"}
                    className={p.enabled ? "bg-green-500" : ""}
                  >
                    {p.enabled ? <CheckIcon className="size-3 mr-1" /> : <XIcon className="size-3 mr-1" />}
                    {p.enabled ? "enabled" : "off"}
                  </Badge>
                </div>
                <CardDescription className="text-xs flex items-center gap-2">
                  <Badge variant="outline" className="text-[10px]">{p.mode}</Badge>
                  <span>·</span>
                  <span>
                    Slots: {p.scheduleSlots.length > 0 ? p.scheduleSlots.join(", ") : "—"}
                  </span>
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm flex-1">
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-muted-foreground block">Replies (24h)</span>
                    <span className="text-foreground">
                      {p.replies} / {p.maxRepliesPerDay}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">Posts (24h)</span>
                    <span className="text-foreground">
                      {p.posts} / {p.maxPostsPerDay}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">Errors</span>
                    <span className={p.errors > 0 ? "text-destructive" : "text-foreground"}>
                      {p.errors}
                    </span>
                  </div>
                </div>
                <div className="text-xs text-muted-foreground">
                  Last run:{" "}
                  {p.lastRun
                    ? `${p.lastRun.startedAt.toLocaleString("fr-FR")} (${p.lastRun.status})`
                    : "never"}
                </div>
                <Button asChild variant="outline" size="sm" className="mt-auto">
                  <Link href={`/dashboard/settings/${p.platform}`}>Configure</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Last cycle + backend status */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Last cycle (any platform)</CardTitle>
            <CardDescription>
              {lastRun
                ? `Started on ${lastRun.startedAt.toLocaleString("fr-FR")}`
                : "No runs yet"}
            </CardDescription>
          </CardHeader>
          {lastRun && (
            <CardContent className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-muted-foreground">Platform</p>
                <Badge variant="outline">{lastRun.platform}</Badge>
              </div>
              <div>
                <p className="text-muted-foreground">Status</p>
                <Badge
                  variant={
                    lastRun.status === "success"
                      ? "default"
                      : lastRun.status === "failed"
                        ? "destructive"
                        : "secondary"
                  }
                >
                  {lastRun.status}
                </Badge>
              </div>
              <div>
                <p className="text-muted-foreground">Trigger</p>
                <p>{lastRun.triggeredBy}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Errors</p>
                <p>{lastRun.errorsCount}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Comments scraped</p>
                <p>{lastRun.commentsScraped}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Replies / Posts</p>
                <p>{lastRun.repliesPosted} / {lastRun.postsPublished}</p>
              </div>
            </CardContent>
          )}
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ActivityIcon className="size-5" /> Backend state
            </CardTitle>
            <CardDescription>Live reading from the worker&apos;s API</CardDescription>
          </CardHeader>
          <CardContent className="text-sm">
            {status ? (
              <ul className="space-y-1">
                <li>
                  <span className="text-muted-foreground">Bot enabled:</span>{" "}
                  {status.bot_enabled ? "yes" : "no"}
                </li>
                <li>
                  <span className="text-muted-foreground">Default ticker:</span>{" "}
                  {status.ticker}
                </li>
                <li>
                  <span className="text-muted-foreground">Trigger pending:</span>{" "}
                  {status.trigger_pending ? "yes" : "no"}
                </li>
                <li>
                  <span className="text-muted-foreground">Shutdown requested:</span>{" "}
                  {status.shutdown_requested ? "yes" : "no"}
                </li>
              </ul>
            ) : (
              <p className="text-muted-foreground">
                Backend unreachable. Check <code>BACKEND_API_URL</code> and{" "}
                <code>BACKEND_API_TOKEN</code>.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
