"use client";

import { useTransition } from "react";
import { Loader, TrashIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { removeWhitelistEntry } from "@/app/(actions)/platforms";

type Props = {
  id: string;     // BigInt serialised
  handle: string;
};

export default function RemoveButton({ id, handle }: Props) {
  const [pending, startTransition] = useTransition();

  function onClick() {
    if (!confirm(`Remove "${handle}" from the whitelist?`)) return;
    startTransition(async () => {
      const res = await removeWhitelistEntry(id);
      if (res.ok) toast.success(`${handle} removed`);
      else toast.error(res.error ?? "Failed to remove entry");
    });
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      disabled={pending}
      onClick={onClick}
      className="text-destructive hover:text-destructive"
    >
      {pending ? <Loader className="animate-spin" /> : <TrashIcon className="size-4" />}
    </Button>
  );
}
