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

const PAGE_SIZE = 50;

function statusBadge(status: string) {
  if (status === "success") return <Badge variant="default" className="bg-green-500">{status}</Badge>;
  if (status === "failed") return <Badge variant="destructive">{status}</Badge>;
  return <Badge className="bg-orange-500">{status}</Badge>;
}

type SearchParams = Promise<{
  page?: string;
  type?: string;
  status?: string;
  platform?: string;
}>;

export default async function ActivitiesPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page ?? 1));
  const skip = (page - 1) * PAGE_SIZE;

  const where: { type?: string; status?: string; platform?: string } = {};
  if (sp.type) where.type = sp.type;
  if (sp.status) where.status = sp.status;
  if (sp.platform) where.platform = sp.platform;

  const [items, total, platforms] = await Promise.all([
    prisma.botActivity.findMany({
      where,
      orderBy: { createdAt: "desc" },
      skip,
      take: PAGE_SIZE,
    }),
    prisma.botActivity.count({ where }),
    listPlatformOptions(),
  ]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function pageHref(p: number) {
    const params = new URLSearchParams();
    if (sp.type) params.set("type", sp.type);
    if (sp.status) params.set("status", sp.status);
    if (sp.platform) params.set("platform", sp.platform);
    params.set("page", String(p));
    return `/dashboard/activities?${params.toString()}`;
  }

  function filterHref(key: "type" | "status" | "platform", value: string | null) {
    const params = new URLSearchParams();
    if (sp.type && key !== "type") params.set("type", sp.type);
    if (sp.status && key !== "status") params.set("status", sp.status);
    if (sp.platform && key !== "platform") params.set("platform", sp.platform);
    if (value) params.set(key, value);
    return `/dashboard/activities${params.toString() ? `?${params.toString()}` : ""}`;
  }

  function chipClass(active: boolean) {
    return active
      ? "rounded bg-primary text-primary-foreground px-2 py-0.5"
      : "rounded border px-2 py-0.5 hover:bg-accent";
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Activities</h1>
        <p className="text-sm text-muted-foreground">
          {total} event{total > 1 ? "s" : ""} — page {page} / {totalPages}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Platform:</span>
        <Link href={filterHref("platform", null)} className={chipClass(!sp.platform)}>
          all
        </Link>
        {platforms.map((p) => (
          <Link
            key={p.value}
            href={filterHref("platform", p.value)}
            className={chipClass(sp.platform === p.value)}
          >
            {p.label}
          </Link>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Type:</span>
        {[null, "scrape", "reply", "post", "session", "error"].map((t) => (
          <Link
            key={t ?? "all"}
            href={filterHref("type", t)}
            className={chipClass((sp.type ?? null) === t)}
          >
            {t ?? "all"}
          </Link>
        ))}
        <span className="text-muted-foreground ml-4">Status:</span>
        {[null, "success", "failed", "skipped"].map((s) => (
          <Link
            key={s ?? "all"}
            href={filterHref("status", s)}
            className={chipClass((sp.status ?? null) === s)}
          >
            {s ?? "all"}
          </Link>
        ))}
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[170px]">Date</TableHead>
              <TableHead className="w-[110px]">Platform</TableHead>
              <TableHead className="w-[100px]">Type</TableHead>
              <TableHead className="w-[110px]">Status</TableHead>
              <TableHead>Content / error</TableHead>
              <TableHead className="w-[160px]">Comment ID</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                  No activities found for the selected filters.
                </TableCell>
              </TableRow>
            )}
            {items.map((a) => (
              <TableRow key={a.id.toString()}>
                <TableCell className="text-xs">
                  {a.createdAt.toLocaleString("fr-FR")}
                </TableCell>
                <TableCell className="text-xs">
                  {a.platform ? <Badge variant="outline">{a.platform}</Badge> : "—"}
                </TableCell>
                <TableCell className="text-xs">{a.type}</TableCell>
                <TableCell>{statusBadge(a.status)}</TableCell>
                <TableCell className="max-w-md text-xs">
                  <span className="line-clamp-2">
                    {a.errorMsg ?? a.content ?? "—"}
                  </span>
                </TableCell>
                <TableCell className="text-xs font-mono text-muted-foreground">
                  {a.commentId ?? "—"}
                </TableCell>
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
