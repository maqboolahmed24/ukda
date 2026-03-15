import type { IndexKind } from "@ukde/contracts";
import { NextRequest, NextResponse } from "next/server";

import { revalidateAfterMutation } from "../../../../../../lib/data/invalidation";
import { rebuildProjectIndex } from "../../../../../../lib/indexes";
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

function parseJsonObject(raw: FormDataEntryValue | null): Record<string, unknown> | null {
  if (typeof raw !== "string") {
    return null;
  }
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
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
  const sourceSnapshotJson = parseJsonObject(formData.get("source_snapshot_json"));
  const buildParametersJson = parseJsonObject(formData.get("build_parameters_json"));
  const force = formData.get("force") !== null;

  if (!kind || !sourceSnapshotJson || !buildParametersJson) {
    return redirectTo(`${projectIndexesPath(projectId)}?status=invalid-json`);
  }

  const result = await rebuildProjectIndex(
    projectId,
    kind,
    {
      sourceSnapshotJson,
      buildParametersJson
    },
    { force }
  );
  if (!result.ok || !result.data) {
    return redirectTo(`${projectIndexesPath(projectId)}?status=action-failed`);
  }

  revalidateAfterMutation("indexes.rebuild", {
    projectId,
    indexId: result.data.index.id,
    indexKind: kind
  });
  const status = result.data.created ? "rebuild-created" : "rebuild-existing";
  return redirectTo(
    `${detailPath(projectId, kind, result.data.index.id)}?status=${status}`
  );
}
