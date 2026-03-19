import { NextRequest, NextResponse } from "next/server";

import { cancelAdminRecoveryDrill } from "../../../../../../../lib/recovery";
import { adminRecoveryDrillDetailPath } from "../../../../../../../lib/routes";

function redirectTo(path: string): NextResponse {
  return new NextResponse(null, {
    status: 303,
    headers: { Location: path }
  });
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ drillId: string }> }
) {
  const { drillId } = await context.params;
  const formData = await request.formData();
  const defaultRedirect = adminRecoveryDrillDetailPath(drillId);
  const redirectToPath =
    typeof formData.get("redirectTo") === "string"
      ? String(formData.get("redirectTo")).trim() || defaultRedirect
      : defaultRedirect;

  if (!drillId || !drillId.trim()) {
    return redirectTo(`${defaultRedirect}?status=cancel-invalid`);
  }

  const result = await cancelAdminRecoveryDrill(drillId);
  if (!result.ok || !result.data) {
    return redirectTo(`${redirectToPath}?status=cancel-failed`);
  }

  return redirectTo(`${adminRecoveryDrillDetailPath(result.data.drill.id)}?status=cancel-complete`);
}
