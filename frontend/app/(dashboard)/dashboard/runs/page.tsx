import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import prisma from "@/lib/prisma";
import { listPlatformOptions } from "@/lib/platforms-list";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 30;

function statusBadge(status: string) {
  if (status === "success") return <Badge variant="default" className="bg-green-500">{status}</Badge>;
  if (status === "failed") return <Badge variant="destructive">{status}</Badge>;
  if (status === "running") return <Badge variant="default" className="bg-orange-500">{status}</Badge>;
  return <Badge variant="outline">{status}</Badge>;
}

function durationOf(start: Date, end: Date | null): string {
  if (!end) return "—";
  const ms = end.getTime() - start.getTime();
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

type SearchParams = Promise<{ page?: string; platform?: string }>;

export default async function RunsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page ?? 1));
  const skip = (page - 1) * PAGE_SIZE;

  const where = sp.platform ? { platform: sp.platform } : undefined;

  const [items, total, platforms] = await Promise.all([
    prisma.botRun.findMany({
      where,
      orderBy: { startedAt: "desc" },
      skip,
      take: PAGE_SIZE,
    }),
    prisma.botRun.count({ where }),
    listPlatformOptions(),
  ]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function pageHref(p: number) {
    const params = new URLSearchParams();
    if (sp.platform) params.set("platform", sp.platform);
    params.set("page", String(p));
    return `/dashboard/runs?${params.toString()}`;
  }

  function filterHref(value: string | null) {
    if (!value) return "/dashboard/runs";
    return `/dashboard/runs?platform=${encodeURIComponent(value)}`;
  }

  function chipClass(active: boolean) {
    return active
      ? "rounded bg-primary text-primary-foreground px-2 py-0.5"
      : "rounded border px-2 py-0.5 hover:bg-accent";
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Cycles</h1>
        <p className="text-sm text-muted-foreground">
          {total} cycle{total > 1 ? "s" : ""} — page {page} / {totalPages}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Platform:</span>
        <Link href={filterHref(null)} className={chipClass(!sp.platform)}>
          all
        </Link>
        {platforms.map((p) => (
          <Link
            key={p.value}
            href={filterHref(p.value)}
            className={chipClass(sp.platform === p.value)}
          >
            {p.label}
          </Link>
        ))}
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[170px]">Started</TableHead>
              <TableHead className="w-[110px]">Platform</TableHead>
              <TableHead className="w-[80px]">Duration</TableHead>
              <TableHead className="w-[100px]">Status</TableHead>
              <TableHead className="w-[110px]">Trigger</TableHead>
              <TableHead className="text-right">Scraped</TableHead>
              <TableHead className="text-right">Replies</TableHead>
              <TableHead className="text-right">Posts</TableHead>
              <TableHead className="text-right">Errors</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 && (
              <TableRow>
                <TableCell colSpan={9} className="text-center text-muted-foreground py-8">
                  No cycles found for the selected filters.
                </TableCell>
              </TableRow>
            )}
            {items.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="text-xs">
                  {r.startedAt.toLocaleString("fr-FR")}
                </TableCell>
                <TableCell><Badge variant="outline">{r.platform}</Badge></TableCell>
                <TableCell className="text-xs">
                  {durationOf(r.startedAt, r.endedAt)}
                </TableCell>
                <TableCell>{statusBadge(r.status)}</TableCell>
                <TableCell className="text-xs">{r.triggeredBy}</TableCell>
                <TableCell className="text-right">{r.commentsScraped}</TableCell>
                <TableCell className="text-right">{r.repliesPosted}</TableCell>
                <TableCell className="text-right">{r.postsPublished}</TableCell>
                <TableCell className="text-right">{r.errorsCount}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <Button asChild variant="outline" disabled={page <= 1}>
          <Link href={pageHref(Math.max(1, page - 1))}>Previous</Link>
        </Button>
        <p className="text-sm text-muted-foreground">
          Page {page} / {totalPages}
        </p>
        <Button asChild variant="outline" disabled={page >= totalPages}>
          <Link href={pageHref(Math.min(totalPages, page + 1))}>Next</Link>
        </Button>
      </div>
    </div>
  );
}
