import { NextRequest, NextResponse } from "next/server";

import { revokeAdminRiskAcceptance } from "../../../../../../../lib/security";
import { adminSecurityRiskAcceptanceDetailPath } from "../../../../../../../lib/routes";

function redirectTo(path: string): NextResponse {
  return new NextResponse(null, {
    status: 303,
    headers: { Location: path }
  });
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ riskAcceptanceId: string }> }
) {
  const { riskAcceptanceId } = await context.params;
  const defaultRedirect = adminSecurityRiskAcceptanceDetailPath(riskAcceptanceId);
  const formData = await request.formData();
  const redirectToPath =
    typeof formData.get("redirectTo") === "string"
      ? String(formData.get("redirectTo")).trim() || defaultRedirect
      : defaultRedirect;
  const reason =
    typeof formData.get("reason") === "string"
      ? String(formData.get("reason")).trim()
      : "";

  if (!riskAcceptanceId || !riskAcceptanceId.trim() || !reason) {
    return redirectTo(`${redirectToPath}?status=action-invalid`);
  }

  const result = await revokeAdminRiskAcceptance(riskAcceptanceId, { reason });
  if (!result.ok || !result.data) {
    return redirectTo(`${redirectToPath}?status=action-failed`);
  }
  return redirectTo(`${adminSecurityRiskAcceptanceDetailPath(result.data.id)}?status=revoked`);
}
