import type { CapacityTestKind } from "@ukde/contracts";
import { NextRequest, NextResponse } from "next/server";

import { createAdminCapacityTest } from "../../../../../../lib/capacity";
import {
  adminCapacityTestDetailPath,
  adminCapacityTestsPath
} from "../../../../../../lib/routes";

function redirectTo(path: string): NextResponse {
  return new NextResponse(null, {
    status: 303,
    headers: { Location: path }
  });
}

function parseTestKind(value: FormDataEntryValue | null): CapacityTestKind | null {
  if (value === "LOAD" || value === "SOAK" || value === "BENCHMARK") {
    return value;
  }
  return null;
}

export async function POST(request: NextRequest) {
  const formData = await request.formData();
  const scenarioName =
    typeof formData.get("scenarioName") === "string"
      ? String(formData.get("scenarioName")).trim()
      : "";
  const testKind = parseTestKind(formData.get("testKind"));
  const redirectToPath =
    typeof formData.get("redirectTo") === "string"
      ? String(formData.get("redirectTo")).trim()
      : adminCapacityTestsPath;

  if (!scenarioName || !testKind) {
    return redirectTo(`${redirectToPath}?status=run-invalid`);
  }

  const result = await createAdminCapacityTest({
    scenarioName,
    testKind
  });
  if (!result.ok || !result.data) {
    return redirectTo(`${redirectToPath}?status=run-failed`);
  }

  return redirectTo(`${adminCapacityTestDetailPath(result.data.run.id)}?status=run-created`);
}
