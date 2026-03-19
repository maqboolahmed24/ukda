import type { RecoveryDrillScope } from "@ukde/contracts";
import { NextRequest, NextResponse } from "next/server";

import { createAdminRecoveryDrill } from "../../../../../../lib/recovery";
import {
  adminRecoveryDrillDetailPath,
  adminRecoveryDrillsPath
} from "../../../../../../lib/routes";

function redirectTo(path: string): NextResponse {
  return new NextResponse(null, {
    status: 303,
    headers: { Location: path }
  });
}

function parseScope(value: FormDataEntryValue | null): RecoveryDrillScope | null {
  if (
    value === "QUEUE_REPLAY" ||
    value === "STORAGE_INTERRUPT" ||
    value === "RESTORE_CLEAN_ENV" ||
    value === "FULL_RECOVERY"
  ) {
    return value;
  }
  return null;
}

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const scope = parseScope(formData.get("scope"));
  const redirectToPath =
    typeof formData.get("redirectTo") === "string"
      ? String(formData.get("redirectTo")).trim()
      : adminRecoveryDrillsPath;

  if (!scope) {
    return redirectTo(`${redirectToPath}?status=drill-invalid`);
  }

  const result = await createAdminRecoveryDrill({ scope });
  if (!result.ok || !result.data) {
    return redirectTo(`${redirectToPath}?status=drill-failed`);
  }

  return redirectTo(
    `${adminRecoveryDrillDetailPath(result.data.drill.id)}?status=drill-created`
  );
}
