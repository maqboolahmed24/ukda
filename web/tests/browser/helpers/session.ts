import type { BrowserContext } from "@playwright/test";

import { getBrowserFixtureSessionToken } from "../../../lib/data/browser-regression-fixtures";

const SESSION_COOKIE_NAME =
  process.env.AUTH_COOKIE_NAME?.trim() || "ukde_session";
const CSRF_COOKIE_NAME =
  process.env.AUTH_CSRF_COOKIE_NAME?.trim() || "ukde_csrf";
const FIXTURE_CSRF_TOKEN = "fixture-csrf-token";

export async function seedAuthenticatedSession(
  context: BrowserContext,
  baseURL: string
): Promise<void> {
  const origin = new URL(baseURL);
  const secure = origin.protocol === "https:";
  const sessionToken = getBrowserFixtureSessionToken();

  await context.addCookies([
    {
      name: SESSION_COOKIE_NAME,
      value: sessionToken,
      domain: origin.hostname,
      path: "/",
      httpOnly: true,
      secure,
      sameSite: "Lax"
    },
    {
      name: CSRF_COOKIE_NAME,
      value: FIXTURE_CSRF_TOKEN,
      domain: origin.hostname,
      path: "/",
      httpOnly: false,
      secure,
      sameSite: "Lax"
    }
  ]);
}
