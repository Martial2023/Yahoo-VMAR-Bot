import Link from "next/link";

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

export const dynamic = "force-dynamic";

const PAGE_SIZE = 50;

type SearchParams = Promise<{ page?: string }>;

export default async function CommentsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;
  const page = Math.max(1, Number(sp.page ?? 1));
  const skip = (page - 1) * PAGE_SIZE;

  const [items, total] = await Promise.all([
    prisma.seenComment.findMany({
      orderBy: { scrapedAt: "desc" },
      skip,
      take: PAGE_SIZE,
    }),
    prisma.seenComment.count(),
  ]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Comments seen</h1>
        <p className="text-sm text-muted-foreground">
          {total} comment{total > 1 ? "s" : ""} processed — page {page} / {totalPages}
        </p>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[170px]">Seen at</TableHead>
              <TableHead className="w-[150px]">Author</TableHead>
              <TableHead>Content</TableHead>
              <TableHead className="w-[140px]">ID</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                  No comments found for the selected filters.
                </TableCell>
              </TableRow>
            )}
            {items.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="text-xs">
                  {c.scrapedAt.toLocaleString("fr-FR")}
                </TableCell>
                <TableCell className="text-xs">{c.author || "—"}</TableCell>
                <TableCell className="max-w-2xl text-xs">
                  <span className="line-clamp-3">{c.content}</span>
                </TableCell>
                <TableCell className="text-xs font-mono text-muted-foreground">
                  {c.id}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <Button asChild variant="outline" disabled={page <= 1}>
          <Link href={`/dashboard/comments?page=${Math.max(1, page - 1)}`}>Previous</Link>
        </Button>
        <p className="text-sm text-muted-foreground">
          Page {page} / {totalPages}
        </p>
        <Button asChild variant="outline" disabled={page >= totalPages}>
          <Link href={`/dashboard/comments?page=${Math.min(totalPages, page + 1)}`}>Next</Link>
        </Button>
      </div>
    </div>
  );
}
