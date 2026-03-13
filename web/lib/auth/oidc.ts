import { createHash, randomBytes } from "node:crypto";

const OIDC_STATE_COOKIE = "ukde_oidc_state";
const OIDC_NONCE_COOKIE = "ukde_oidc_nonce";
const OIDC_CODE_VERIFIER_COOKIE = "ukde_oidc_code_verifier";

export function getOidcStateCookieName(): string {
  return OIDC_STATE_COOKIE;
}

export function getOidcNonceCookieName(): string {
  return OIDC_NONCE_COOKIE;
}

export function getOidcCodeVerifierCookieName(): string {
  return OIDC_CODE_VERIFIER_COOKIE;
}

function toBase64Url(input: Buffer): string {
  return input
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

export function generateVerifier(length = 64): string {
  return toBase64Url(randomBytes(length)).slice(0, 96);
}

export function generateStateToken(length = 24): string {
  return toBase64Url(randomBytes(length)).slice(0, 48);
}

export function generateCodeChallenge(verifier: string): string {
  return createHash("sha256").update(verifier).digest("base64url");
}
