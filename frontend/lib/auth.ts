import { betterAuth } from "better-auth";
import { prismaAdapter } from "better-auth/adapters/prisma";
import { nextCookies } from "better-auth/next-js";
import { resend } from "./resend";
import prisma from "./prisma";

const trustedOrigins = [process.env.BETTER_AUTH_URL ?? "http://localhost:3000"];

export const auth = betterAuth({
  trustedOrigins,
  secret: process.env.BETTER_AUTH_SECRET,
  database: prismaAdapter(prisma, {
    provider: "postgresql",
  }),
  emailAndPassword: {
    enabled: true,
    disableSignUp: false,
    requireEmailVerification: false,
    sendResetPassword: async ({ user, url }) => {
      if (!process.env.RESEND_API_KEY) {
        console.warn("[auth] RESEND_API_KEY missing — reset link:", url);
        return;
      }
      const { error } = await resend.emails.send({
        from: process.env.RESEND_FROM ?? "onboarding@resend.dev",
        to: user.email,
        subject: "Réinitialiser votre mot de passe",
        html: `<p>Cliquez sur le lien ci-dessous pour réinitialiser votre mot de passe :</p><p><a href="${url}">${url}</a></p>`,
      });
      if (error) console.error("[Resend] Reset password email error:", error);
    },
  },
  plugins: [nextCookies()],
});
