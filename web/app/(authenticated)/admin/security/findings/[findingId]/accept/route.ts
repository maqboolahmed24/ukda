import { NextRequest, NextResponse } from "next/server";

import { createAdminRiskAcceptance } from "../../../../../../../lib/security";
import {
  adminSecurityFindingDetailPath,
  adminSecurityRiskAcceptanceDetailPath
} from "../../../../../../../lib/routes";

function redirectTo(path: string): NextResponse {
  return new NextResponse(null, {
    status: 303,
    headers: { Location: path }
  });
}

function parseDateTimeInput(value: FormDataEntryValue | null): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed.toISOString();
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ findingId: string }> }
) {
  const { findingId } = await context.params;
  const defaultRedirect = adminSecurityFindingDetailPath(findingId);
  const formData = await request.formData();
  const redirectToPath =
    typeof formData.get("redirectTo") === "string"
      ? String(formData.get("redirectTo")).trim() || defaultRedirect
      : defaultRedirect;
  const justification =
    typeof formData.get("justification") === "string"
      ? String(formData.get("justification")).trim()
      : "";
  const expiresAt = parseDateTimeInput(formData.get("expiresAt"));
  const reviewDate = parseDateTimeInput(formData.get("reviewDate"));

  if (!findingId || !findingId.trim()) {
    return redirectTo(`${defaultRedirect}?status=accept-invalid`);
  }
  if (!justification || (!expiresAt && !reviewDate)) {
    return redirectTo(`${redirectToPath}?status=accept-invalid`);
  }

  const result = await createAdminRiskAcceptance(findingId, {
    justification,
    expiresAt,
    reviewDate
  });
  if (!result.ok || !result.data) {
    return redirectTo(`${redirectToPath}?status=accept-failed`);
  }
  return redirectTo(
    `${adminSecurityRiskAcceptanceDetailPath(result.data.id)}?status=created`
  );
}
