import { NextResponse } from "next/server";

import { getProjectIndexStatus } from "../../../../../../../../lib/indexes";

export async function GET(
  _request: Request,
  context: { params: Promise<{ projectId: string; indexId: string }> }
) {
  const { projectId, indexId } = await context.params;
  const result = await getProjectIndexStatus(projectId, "SEARCH", indexId);
  if (!result.ok) {
    return NextResponse.json(
      { detail: result.detail ?? "Index status unavailable." },
      { status: result.status || 503 }
    );
  }
  return NextResponse.json(result.data, { status: 200 });
}
