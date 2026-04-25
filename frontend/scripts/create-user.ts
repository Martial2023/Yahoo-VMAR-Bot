/**
 * Bootstrap admin user — bypasses HTTP signup (disableSignUp: true).
 *
 *   pnpm tsx scripts/create-user.ts <email> <password> [name]
 *   pnpm tsx scripts/create-user.ts admin@vmar.local "MyStrongPass123" "Admin"
 *
 * Calls auth.api.signUpEmail() directly server-side, which is not subject
 * to the HTTP-level disableSignUp flag.
 */
import "dotenv/config";
import { auth } from "../lib/auth";

async function main() {
  const [email, password, name = "Admin"] = process.argv.slice(2);
  if (!email || !password) {
    console.error("Usage: pnpm tsx scripts/create-user.ts <email> <password> [name]");
    process.exit(1);
  }
  if (password.length < 8) {
    console.error("Password must be at least 8 characters.");
    process.exit(1);
  }
  try {
    const result = await auth.api.signUpEmail({
      body: { email, password, name },
    });
    console.log("✓ User created:", result.user?.email ?? email);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("Error creating user:", msg);
    process.exit(1);
  }
}

main();
