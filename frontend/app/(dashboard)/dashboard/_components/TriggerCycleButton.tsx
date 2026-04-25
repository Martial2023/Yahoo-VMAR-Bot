"use client";

import { useTransition } from "react";
import { Loader, PlayIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { runCycleNow } from "@/app/(actions)/actions";

export function TriggerCycleButton() {
  const [pending, startTransition] = useTransition();

  return (
    <Button
      onClick={() =>
        startTransition(async () => {
          const res = await runCycleNow();
          if (res.ok) toast.success("Cycle triggered — the worker is executing it now");
          else toast.error(res.error ?? "Error");
        })
      }
      disabled={pending}
    >
      {pending ? <Loader className="animate-spin" /> : <PlayIcon />}
      Run cycle now
    </Button>
  );
}
