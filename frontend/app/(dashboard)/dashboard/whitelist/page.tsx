import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import prisma from "@/lib/prisma";

import WhitelistAddForm from "./_components/WhitelistAddForm";
import RemoveButton from "./_components/RemoveButton";

export const dynamic = "force-dynamic";

type SearchParams = Promise<{ platform?: string }>;

export default async function WhitelistPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;
  const filterPlatform = sp.platform || null;

  const [platforms, entries] = await Promise.all([
    prisma.platformSettings.findMany({
      orderBy: { platform: "asc" },
      select: { platform: true, displayName: true },
    }),
    prisma.whitelistedAuthor.findMany({
      where: filterPlatform ? { platform: filterPlatform } : undefined,
      orderBy: [{ platform: "asc" }, { createdAt: "desc" }],
    }),
  ]);

  function filterHref(platform: string | null) {
    if (!platform) return "/dashboard/whitelist";
    return `/dashboard/whitelist?platform=${encodeURIComponent(platform)}`;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Whitelisted Authors</h1>
        <p className="text-sm text-muted-foreground">
          When a platform is in <strong>test</strong> mode, the bot only replies
          to authors listed here for that platform. Add yourself / colleagues
          before activating a new platform.
        </p>
      </div>

      <WhitelistAddForm
        platforms={platforms.map((p) => ({ value: p.platform, label: p.displayName }))}
        defaultPlatform={filterPlatform ?? platforms[0]?.platform ?? ""}
      />

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Platform:</span>
        <Link
          href={filterHref(null)}
          className={
            filterPlatform === null
              ? "rounded bg-primary text-primary-foreground px-2 py-0.5"
              : "rounded border px-2 py-0.5 hover:bg-accent"
          }
        >
          all
        </Link>
        {platforms.map((p) => (
          <Link
            key={p.platform}
            href={filterHref(p.platform)}
            className={
              filterPlatform === p.platform
                ? "rounded bg-primary text-primary-foreground px-2 py-0.5"
                : "rounded border px-2 py-0.5 hover:bg-accent"
            }
          >
            {p.displayName}
          </Link>
        ))}
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[160px]">Platform</TableHead>
              <TableHead>Handle</TableHead>
              <TableHead>Note</TableHead>
              <TableHead className="w-[170px]">Added</TableHead>
              <TableHead className="w-[100px] text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                  No whitelisted authors
                  {filterPlatform ? ` for ${filterPlatform}` : ""} yet.
                </TableCell>
              </TableRow>
            )}
            {entries.map((e) => (
              <TableRow key={e.id.toString()}>
                <TableCell>
                  <Badge variant="outline">{e.platform}</Badge>
                </TableCell>
                <TableCell className="font-mono text-sm">{e.authorHandle}</TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {e.note ?? "—"}
                </TableCell>
                <TableCell className="text-xs">
                  {e.createdAt.toLocaleString("fr-FR")}
                </TableCell>
                <TableCell className="text-right">
                  <RemoveButton id={e.id.toString()} handle={e.authorHandle} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
