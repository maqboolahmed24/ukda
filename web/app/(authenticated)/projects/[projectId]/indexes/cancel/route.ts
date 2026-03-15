import type { IndexKind } from "@ukde/contracts";
import { NextRequest, NextResponse } from "next/server";

import { revalidateAfterMutation } from "../../../../../../lib/data/invalidation";
import { cancelProjectIndex } from "../../../../../../lib/indexes";
import {
  projectDerivativeIndexPath,
  projectEntityIndexPath,
  projectIndexesPath,
  projectSearchIndexPath
} from "../../../../../../lib/routes";

function redirectTo(path: string, status = 303): NextResponse {
  return new NextResponse(null, {
    status,
    headers: { Location: path }
  });
}

function parseKind(raw: FormDataEntryValue | null): IndexKind | null {
  if (raw === "SEARCH" || raw === "ENTITY" || raw === "DERIVATIVE") {
    return raw;
  }
  return null;
}

function detailPath(projectId: string, kind: IndexKind, indexId: string): string {
  if (kind === "SEARCH") {
    return projectSearchIndexPath(projectId, indexId);
  }
  if (kind === "ENTITY") {
    return projectEntityIndexPath(projectId, indexId);
  }
  return projectDerivativeIndexPath(projectId, indexId);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  const formData = await request.formData();
  const kind = parseKind(formData.get("kind"));
  const indexId = formData.get("index_id");
  if (!kind || typeof indexId !== "string" || indexId.trim().length === 0) {
    return redirectTo(`${projectIndexesPath(projectId)}?status=action-failed`);
  }

  const result = await cancelProjectIndex(projectId, kind, indexId);
  if (!result.ok || !result.data) {
    return redirectTo(`${projectIndexesPath(projectId)}?status=action-failed`);
  }
  revalidateAfterMutation("indexes.cancel", {
    projectId,
    indexKind: kind,
    indexId
  });
  return redirectTo(
    `${detailPath(projectId, kind, indexId)}?status=${
      result.data.terminal ? "cancel-terminal" : "cancel-requested"
    }`
  );
}
