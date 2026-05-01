"use client";

import { useState, useTransition } from "react";
import { Loader, PlusIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { addWhitelistEntry } from "@/app/(actions)/platforms";

type Props = {
  platforms: { value: string; label: string }[];
  defaultPlatform: string;
};

export default function WhitelistAddForm({ platforms, defaultPlatform }: Props) {
  const [pending, startTransition] = useTransition();
  const [platform, setPlatform] = useState(defaultPlatform);
  const [handle, setHandle] = useState("");
  const [note, setNote] = useState("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!handle.trim()) {
      toast.error("Handle is required");
      return;
    }
    startTransition(async () => {
      const res = await addWhitelistEntry(platform, handle, note || null);
      if (res.ok) {
        toast.success(`${handle} added to ${platform} whitelist`);
        setHandle("");
        setNote("");
      } else {
        toast.error(res.error ?? "Failed to add entry");
      }
    });
  }

  return (
    <form
      onSubmit={onSubmit}
      className="grid gap-3 rounded-lg border p-4 md:grid-cols-[200px_1fr_1fr_auto] md:items-end"
    >
      <div className="grid gap-2">
        <Label className="text-xs">Platform</Label>
        <Select value={platform} onValueChange={setPlatform}>
          <SelectTrigger className="cursor-pointer">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {platforms.map((p) => (
              <SelectItem key={p.value} value={p.value}>
                {p.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="grid gap-2">
        <Label className="text-xs">Author handle</Label>
        <Input
          value={handle}
          onChange={(e) => setHandle(e.target.value)}
          placeholder="reddit_username, yahoo_handle, ..."
        />
      </div>
      <div className="grid gap-2">
        <Label className="text-xs">Note (optional)</Label>
        <Input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="my test account"
        />
      </div>
      <Button type="submit" disabled={pending}>
        {pending ? <Loader className="animate-spin" /> : <PlusIcon />}
        Add
      </Button>
    </form>
  );
}
