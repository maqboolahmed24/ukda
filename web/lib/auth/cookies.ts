import { cookies } from "next/headers";

const FALLBACK_SESSION_COOKIE = "ukde_session";
const FALLBACK_CSRF_COOKIE = "ukde_csrf";

export function getSessionCookieName(): string {
  return process.env.AUTH_COOKIE_NAME?.trim() || FALLBACK_SESSION_COOKIE;
}

export function getCsrfCookieName(): string {
  return process.env.AUTH_CSRF_COOKIE_NAME?.trim() || FALLBACK_CSRF_COOKIE;
}

export function shouldUseSecureCookies(): boolean {
  const appEnv = (
    process.env.APP_ENV ||
    process.env.NEXT_PUBLIC_APP_ENV ||
    "dev"
  ).toLowerCase();
  return appEnv === "staging" || appEnv === "prod";
}

export async function readSessionToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(getSessionCookieName())?.value ?? null;
}

export async function readCsrfToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(getCsrfCookieName())?.value ?? null;
}

