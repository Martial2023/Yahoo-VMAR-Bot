import { notFound } from "next/navigation";

import prisma from "@/lib/prisma";

import SettingsForm from "./_components/SettingsForm";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const settings = await prisma.botSettings.findUnique({ where: { id: 1 } });
  if (!settings) notFound();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Paramètres du bot</h1>
        <p className="text-sm text-muted-foreground">
          Modifications appliquées au prochain cycle (ou immédiatement via le backend)
        </p>
      </div>
      <SettingsForm
        initial={{
          botEnabled: settings.botEnabled,
          mode: settings.mode as "reply" | "post" | "both",
          ticker: settings.ticker,
          checkIntervalMin: settings.checkIntervalMin,
          checkIntervalMax: settings.checkIntervalMax,
          maxRepliesPerHour: settings.maxRepliesPerHour,
          maxPostsPerDay: settings.maxPostsPerDay,
          aiModel: settings.aiModel,
          aiTemperature: settings.aiTemperature,
          replyPrompt: settings.replyPrompt,
          postPrompt: settings.postPrompt,
          alertEmails: settings.alertEmails,
        }}
      />
    </div>
  );
}
