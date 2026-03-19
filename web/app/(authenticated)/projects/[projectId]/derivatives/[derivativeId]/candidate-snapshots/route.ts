import { NextRequest, NextResponse } from "next/server";

import { revalidateAfterMutation } from "../../../../../../../lib/data/invalidation";
import { createProjectDerivativeCandidateSnapshot } from "../../../../../../../lib/derivatives";
import {
  projectDerivativePath,
  projectDerivativePreviewPath
} from "../../../../../../../lib/routes";

function redirectTo(path: string, status = 303): NextResponse {
  return new NextResponse(null, {
    status,
    headers: { Location: path }
  });
}

function resolveReturnPath(
  request: NextRequest,
  projectId: string,
  derivativeId: string
): string {
  const fallback = projectDerivativePath(projectId, derivativeId);
  const referer = request.headers.get("referer");
  if (!referer) {
    return fallback;
  }
  try {
    const parsed = new URL(referer);
    const previewPath = projectDerivativePreviewPath(projectId, derivativeId);
    if (parsed.pathname === previewPath) {
      return previewPath;
    }
    if (parsed.pathname === fallback) {
      return fallback;
    }
  } catch {
    return fallback;
  }
  return fallback;
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId: string; derivativeId: string }> }
) {
  const { projectId, derivativeId } = await context.params;
  const returnPath = resolveReturnPath(request, projectId, derivativeId);

  const result = await createProjectDerivativeCandidateSnapshot(
    projectId,
    derivativeId
  );
  if (!result.ok || !result.data) {
    return redirectTo(`${returnPath}?status=freeze-failed`);
  }

  revalidateAfterMutation("derivatives.freeze", {
    projectId,
    indexId: derivativeId
  });
  return redirectTo(
    `${returnPath}?status=${result.data.created ? "frozen" : "freeze-existing"}`
  );
}
