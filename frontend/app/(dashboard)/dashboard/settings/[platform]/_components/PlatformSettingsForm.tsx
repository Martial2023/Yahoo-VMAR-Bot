"use client";

import { useState, useTransition } from "react";
import { KeyRoundIcon, Loader, PlayIcon, SaveIcon } from "lucide-react";
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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  loginPlatform,
  runPlatformCycle,
  togglePlatform,
  updatePlatformSettings,
  type PlatformSettingsInput,
} from "@/app/(actions)/platforms";

type Props = {
  platform: string;
  displayName: string;
  initial: PlatformSettingsInput;
};

const SLOT_RE = /^([01]?\d|2[0-3]):[0-5]\d$/;

export default function PlatformSettingsForm({ platform, displayName, initial }: Props) {
  const [pending, startTransition] = useTransition();
  const [triggerPending, startTriggerTransition] = useTransition();
  const [loginPending, startLoginTransition] = useTransition();
  const [form, setForm] = useState<PlatformSettingsInput>(initial);
  const [slotsRaw, setSlotsRaw] = useState(initial.scheduleSlots.join("\n"));

  // Parse credentials JSON into typed fields for the UI
  const parsedCreds = (() => {
    try { return JSON.parse(initial.credentialsJson || "{}"); }
    catch { return {}; }
  })();
  const [credEmail, setCredEmail] = useState<string>(parsedCreds.email ?? "");
  const [credPassword, setCredPassword] = useState<string>(parsedCreds.password ?? "");

  // Whether this platform needs a password (Reddit uses magic links — no password)
  const needsPassword = platform !== "reddit";

  function field<K extends keyof PlatformSettingsInput>(
    key: K,
    value: PlatformSettingsInput[K],
  ) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function onToggleEnabled(enabled: boolean) {
    field("enabled", enabled);
    startTransition(async () => {
      const res = await togglePlatform(platform, enabled);
      if (res.ok) toast.success(`${displayName} ${enabled ? "enabled" : "disabled"}`);
      else toast.error("Toggle failed");
    });
  }

  async function onTriggerNow() {
    startTriggerTransition(async () => {
      const res = await runPlatformCycle(platform);
      if (res.ok) toast.success(res.detail ?? "Cycle queued");
      else toast.error(res.error ?? "Failed to trigger cycle");
    });
  }

  async function onLoginNow() {
    startLoginTransition(async () => {
      const res = await loginPlatform(platform);
      if (res.ok) toast.success(res.detail ?? "Login successful");
      else toast.error(res.error ?? "Login failed — check backend logs");
    });
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const scheduleSlots = slotsRaw
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);

    const invalid = scheduleSlots.find((s) => !SLOT_RE.test(s));
    if (invalid) {
      toast.error(`Invalid slot "${invalid}" — expected HH:MM`);
      return;
    }

    // Build credentials JSON from typed fields
    const creds: Record<string, string> = {};
    if (credEmail.trim()) creds.email = credEmail.trim();
    if (needsPassword && credPassword.trim()) creds.password = credPassword.trim();
    const credentialsJson = Object.keys(creds).length > 0
      ? JSON.stringify(creds, null, 2)
      : "";

    startTransition(async () => {
      const res = await updatePlatformSettings(platform, {
        ...form,
        scheduleSlots,
        credentialsJson,
      });
      if (res.ok) toast.success("Platform settings saved");
      else toast.error(res.error ?? "Error saving settings");
    });
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-6">
      {/* Status row */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex items-center justify-between rounded-lg border p-4">
          <div>
            <Label className="text-base">Enabled</Label>
            <p className="text-sm text-muted-foreground">
              When off, the worker skips this platform entirely
            </p>
          </div>
          <Switch
            className="cursor-pointer"
            checked={form.enabled}
            onCheckedChange={onToggleEnabled}
          />
        </div>

        <div className="flex items-center justify-between rounded-lg border p-4">
          <div>
            <Label className="text-base">Trigger cycle now</Label>
            <p className="text-sm text-muted-foreground">
              Runs <strong>{platform}</strong> immediately, ignoring schedule
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={triggerPending || !form.enabled}
            onClick={onTriggerNow}
          >
            {triggerPending ? <Loader className="animate-spin" /> : <PlayIcon />}
            Run now
          </Button>
        </div>
      </div>

      {/* Mode + features */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="grid gap-2">
          <Label>Mode</Label>
          <Select
            value={form.mode}
            onValueChange={(v) => field("mode", v as PlatformSettingsInput["mode"])}
          >
            <SelectTrigger className="w-full cursor-pointer">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="test">Test (whitelist only)</SelectItem>
              <SelectItem value="production">Production (all authors)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center justify-between rounded-lg border p-3">
          <Label>Reply enabled</Label>
          <Switch
            className="cursor-pointer"
            checked={form.replyEnabled}
            onCheckedChange={(v) => field("replyEnabled", v)}
          />
        </div>
        <div className="flex items-center justify-between rounded-lg border p-3">
          <Label>Post enabled</Label>
          <Switch
            className="cursor-pointer"
            checked={form.postEnabled}
            onCheckedChange={(v) => field("postEnabled", v)}
          />
        </div>
      </div>

      {/* Quotas + ticker */}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="grid gap-2">
          <Label>Ticker</Label>
          <Input
            value={form.ticker}
            onChange={(e) => field("ticker", e.target.value.toUpperCase())}
          />
        </div>
        <div className="grid gap-2">
          <Label>Max replies / day</Label>
          <Input
            type="number"
            min={0}
            value={form.maxRepliesPerDay}
            onChange={(e) => field("maxRepliesPerDay", Number(e.target.value))}
          />
        </div>
        <div className="grid gap-2">
          <Label>Max posts / day</Label>
          <Input
            type="number"
            min={0}
            value={form.maxPostsPerDay}
            onChange={(e) => field("maxPostsPerDay", Number(e.target.value))}
          />
        </div>
        <div className="grid gap-2">
          <Label>Min post length</Label>
          <Input
            type="number"
            min={0}
            value={form.minPostLength}
            onChange={(e) => field("minPostLength", Number(e.target.value))}
          />
        </div>
      </div>

      {/* Schedule */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="grid gap-2 md:col-span-2">
          <Label>Schedule slots (one HH:MM per line, server timezone)</Label>
          <Textarea
            rows={4}
            value={slotsRaw}
            onChange={(e) => setSlotsRaw(e.target.value)}
            placeholder={"09:00\n14:00\n19:00"}
            className="font-mono text-sm"
          />
          <p className="text-xs text-muted-foreground">
            Empty = the platform never fires automatically (manual triggers only).
          </p>
        </div>
        <div className="grid gap-2">
          <Label>Schedule jitter (minutes)</Label>
          <Input
            type="number"
            min={1}
            value={form.scheduleJitterMin}
            onChange={(e) => field("scheduleJitterMin", Number(e.target.value))}
          />
          <p className="text-xs text-muted-foreground">
            Width of the window after each slot during which the cycle may fire.
          </p>
        </div>
      </div>

      {/* Prompts */}
      <div className="grid gap-2">
        <Label>System Prompt — Replies (overrides global)</Label>
        <Textarea
          rows={8}
          value={form.replyPrompt ?? ""}
          onChange={(e) => field("replyPrompt", e.target.value || null)}
          placeholder="Leave blank to inherit the global reply prompt"
          className="max-h-48 overflow-y-auto"
        />
      </div>

      <div className="grid gap-2">
        <Label>System Prompt — Proactive Posts (overrides global)</Label>
        <Textarea
          rows={8}
          value={form.postPrompt ?? ""}
          onChange={(e) => field("postPrompt", e.target.value || null)}
          placeholder="Leave blank to inherit the global post prompt"
          className="max-h-48 overflow-y-auto"
        />
      </div>

      {/* Credentials + Login */}
      <div className="rounded-lg border p-4 grid gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold">Account Credentials</h3>
            <p className="text-xs text-muted-foreground">
              {platform === "reddit"
                ? "Email linked to the Reddit account (magic link login)."
                : "Email and password for the bot account on this platform."}
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={loginPending || !credEmail.trim()}
            onClick={onLoginNow}
          >
            {loginPending ? <Loader className="animate-spin" /> : <KeyRoundIcon className="size-4" />}
            Login Now
          </Button>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="grid gap-2">
            <Label>Email</Label>
            <Input
              type="email"
              value={credEmail}
              onChange={(e) => setCredEmail(e.target.value)}
              placeholder="bot@example.com"
            />
          </div>
          {needsPassword && (
            <div className="grid gap-2">
              <Label>Password</Label>
              <Input
                type="password"
                value={credPassword}
                onChange={(e) => setCredPassword(e.target.value)}
                placeholder="platform password"
              />
            </div>
          )}
        </div>
      </div>

      {/* Platform config (JSON) */}
      <div className="grid gap-2">
        <Label>Platform config (JSON)</Label>
        <Textarea
          rows={6}
          value={form.configJson}
          onChange={(e) => field("configJson", e.target.value)}
          placeholder={`{\n  "searchQueries": ["VMAR"],\n  "skipAuthors": ["automoderator"]\n}`}
          className="font-mono text-xs max-h-48 overflow-y-auto"
        />
        <p className="text-xs text-muted-foreground">
          Adapter-specific options (searchQueries, skipAuthors, skipKeywords, …)
        </p>
      </div>

      <div className="flex flex-wrap gap-3 w-full">
        <Button type="submit" disabled={pending} className="min-w-32 w-full">
          {pending ? <Loader className="animate-spin" /> : <SaveIcon />}
          Save Settings
        </Button>
      </div>
    </form>
  );
}
