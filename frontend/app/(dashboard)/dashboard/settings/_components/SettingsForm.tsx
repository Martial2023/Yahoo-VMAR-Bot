"use client";

import { useState, useTransition } from "react";
import { Loader, SaveIcon } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { updateBotSettings, type SettingsInput } from "@/app/(actions)/actions";
import { AI_MODELS, AI_PROVIDERS, findModelByOpenrouterId } from "@/lib/ai-models";

type Props = {
  initial: SettingsInput;
};

export default function SettingsForm({ initial }: Props) {
  const [pending, startTransition] = useTransition();
  const [form, setForm] = useState<SettingsInput>(initial);
  const [emailsRaw, setEmailsRaw] = useState(initial.alertEmails.join(", "));

  function field<K extends keyof SettingsInput>(key: K, value: SettingsInput[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const emails = emailsRaw
      .split(/[,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);

    startTransition(async () => {
      const res = await updateBotSettings({ ...form, alertEmails: emails });
      if (res.ok) toast.success("Settings saved — backend reloaded");
      else toast.error(res.error ?? "Error saving settings");
    });
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-6">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex items-center justify-between rounded-lg border p-4">
          <div>
            <Label className="text-base">Bot Enabled</Label>
            <p className="text-sm text-muted-foreground">
              If disabled, the worker will skip cycles
            </p>
          </div>
          <Switch
            className="cursor-pointer"
            checked={form.botEnabled}
            onCheckedChange={(v) => field("botEnabled", v)}
          />
        </div>

        <div className="grid gap-2">
          <Label>Mode</Label>
          <Select value={form.mode} onValueChange={(v) => field("mode", v as SettingsInput["mode"])}>
            <SelectTrigger className="w-full cursor-pointer">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="reply">Only Replies</SelectItem>
              <SelectItem value="post">Only Proactive Posts</SelectItem>
              <SelectItem value="both">Both</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="grid gap-2">
          <Label>Ticker</Label>
          <Input
            value={form.ticker}
            onChange={(e) => field("ticker", e.target.value.toUpperCase())}
          />
        </div>

        <div className="grid gap-2">
          <Label>AI Model (OpenRouter)</Label>
          <Select
            value={form.aiModel}
            onValueChange={(v) => field("aiModel", v)}
          >
            <SelectTrigger className="w-full cursor-pointer">
              <SelectValue placeholder="Select a model">
                {findModelByOpenrouterId(form.aiModel)?.name ?? form.aiModel}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {AI_PROVIDERS.map((provider) => (
                <SelectGroup key={provider}>
                  <SelectLabel>{provider}</SelectLabel>
                  {AI_MODELS.filter((m) => m.provider === provider).map((m) => (
                    <SelectItem key={m.id} value={m.openrouterId}>
                      {m.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="grid gap-2">
          <Label>AI Temperature</Label>
          <Input
            type="number"
            step="0.1"
            min={0}
            max={2}
            value={form.aiTemperature}
            onChange={(e) => field("aiTemperature", Number(e.target.value))}
          />
        </div>

        <div className="grid gap-2">
          <Label>Check Interval Min (seconds)</Label>
          <Input
            type="number"
            min={30}
            value={form.checkIntervalMin}
            onChange={(e) => field("checkIntervalMin", Number(e.target.value))}
          />
        </div>

        <div className="grid gap-2">
          <Label>Check Interval Max (seconds)</Label>
          <Input
            type="number"
            min={30}
            value={form.checkIntervalMax}
            onChange={(e) => field("checkIntervalMax", Number(e.target.value))}
          />
        </div>

        <div className="grid gap-2">
          <Label>Max Replies / Hour</Label>
          <Input
            type="number"
            min={0}
            value={form.maxRepliesPerHour}
            onChange={(e) => field("maxRepliesPerHour", Number(e.target.value))}
          />
        </div>

        <div className="w-full">
          <Label>Max Posts / Day</Label>
          <Input
            type="number"
            min={0}
            value={form.maxPostsPerDay}
            onChange={(e) => field("maxPostsPerDay", Number(e.target.value))}
          />
        </div>

        <div className="grid gap-2 md:col-span-2">
          <Label>Alert Emails (comma or space separated)</Label>
          <Input
            value={emailsRaw}
            onChange={(e) => setEmailsRaw(e.target.value)}
            placeholder="alerte@vmar.local, ops@vmar.local"
          />
        </div>
      </div>

      <div className="grid gap-2">
        <Label>System Prompt — Replies</Label>
        <Textarea
          rows={10}
          value={form.replyPrompt}
          onChange={(e) => field("replyPrompt", e.target.value)}
          className="max-h-48 overflow-y-auto"
        />
      </div>

      <div className="grid gap-2">
        <Label>System Prompt — Proactive Posts</Label>
        <Textarea
          rows={10}
          value={form.postPrompt}
          onChange={(e) => field("postPrompt", e.target.value)}
          className="max-h-48 overflow-y-auto"
        />
      </div>

      <div className="w-full md:w-auto">
        <Button type="submit" disabled={pending} className="w-full">
          {pending ? <Loader className="animate-spin" /> : <SaveIcon />}
          Save Settings
        </Button>
      </div>
    </form>
  );
}
