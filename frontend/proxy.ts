import { NextRequest, NextResponse } from "next/server";
import { headers } from "next/headers";
import { auth } from "@/lib/auth";

const PUBLIC_ROUTES = ["/", "/about", "/contact"];
const AUTH_ROUTES = ["/sign-in", "/sign-up", "/forgot-password", "/reset-password"];
const ADMIN_PREFIX = "/admin";
const API_ROUTES_PREFIX = "/api";

// Liste des extensions à exclure manuellement si Next les route via le proxy
const STATIC_EXTENSIONS = [
  ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
  ".ico", ".css", ".js", ".woff", ".woff2", ".ttf"
];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 1. Ignore fichiers statiques
  if (STATIC_EXTENSIONS.some(ext => pathname.endsWith(ext))) {
    return NextResponse.next();
  }

  // 2. Ignore tout ce qui est dans _next/ ou _static (rarement envoyé au proxy mais safe)
  if (pathname.startsWith("/_next") || pathname.startsWith("/_static")) {
    return NextResponse.next();
  }

  // 3. Ignore API
  if (pathname.startsWith(API_ROUTES_PREFIX)) {
    return NextResponse.next();
  }

  // 4. Auth logic
  const incomingHeaders = await headers();
  const session = await auth.api.getSession({ headers: incomingHeaders });
  // const role = session?.user?.role;

  // 5. Admin routes protection
  // if (pathname.startsWith(ADMIN_PREFIX)) {
  //   if (role === "ADMIN") {
  //     return NextResponse.next();
  //   }
  //   // Redirect non-admins trying to access admin routes
  //   const url = new URL("/", request.url);
  //   return NextResponse.redirect(url);
  // }

  const isAuthRoute = AUTH_ROUTES.some(route => pathname === route || pathname.startsWith(route + "/"));
  const isPublic = PUBLIC_ROUTES.includes(pathname) || isAuthRoute;

  if (!session && !isPublic) {
    const url = new URL("/sign-in", request.url);
    url.searchParams.set("redirectTo", pathname);
    return NextResponse.redirect(url);
  }

  if (session && isAuthRoute) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}