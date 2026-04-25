import { ActivityIcon, MessageSquareIcon, ReplyIcon, ShieldAlertIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
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

export default async function DashboardPage() {
  const [data, status, health] = await Promise.all([
    getOverview(),
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
          <p className="text-sm text-muted-foreground">
            Bot state
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant={backendOnline ? "default" : "destructive"} className={`${backendOnline && 'bg-green-500'}`}>
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
            <CardDescription>Active Mode</CardDescription>
            <CardTitle className="text-2xl">{settings?.mode ?? "—"}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Ticker : {settings?.ticker ?? "—"}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Responses (24h)</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2">
              <ReplyIcon className="size-5" /> {repliesToday}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            This hour : {repliesLastHour} / {settings?.maxRepliesPerHour ?? "?"}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Posts (24h)</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2">
              <MessageSquareIcon className="size-5" /> {postsToday}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Daily limit : {settings?.maxPostsPerDay ?? "?"}
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
            Comments seen : {seenComments}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Last cycle</CardTitle>
            <CardDescription>
              {lastRun
                ? `Started on ${lastRun.startedAt.toLocaleString("fr-FR")}`
                : "No runs yet"}
            </CardDescription>
          </CardHeader>
          {lastRun && (
            <CardContent className="grid grid-cols-2 gap-3 text-sm">
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
                <p className="text-muted-foreground">Comments Scraped</p>
                <p>{lastRun.commentsScraped}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Replies</p>
                <p>{lastRun.repliesPosted}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Posts</p>
                <p>{lastRun.postsPublished}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Errors</p>
                <p>{lastRun.errorsCount}</p>
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
                  <span className="text-muted-foreground">Bot enabled :</span>{" "}
                  {status.bot_enabled ? "yes" : "no"}
                </li>
                <li>
                  <span className="text-muted-foreground">Mode :</span> {status.mode}
                </li>
                <li>
                  <span className="text-muted-foreground">Ticker :</span> {status.ticker}
                </li>
                <li>
                  <span className="text-muted-foreground">Trigger en attente :</span>{" "}
                  {status.trigger_pending ? "yes" : "no"}
                </li>
                <li>
                  <span className="text-muted-foreground">Shutdown demandé :</span>{" "}
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
