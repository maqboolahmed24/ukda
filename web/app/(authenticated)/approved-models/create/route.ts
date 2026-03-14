import { NextRequest, NextResponse } from "next/server";

import type {
  ApprovedModelRole,
  ApprovedModelServingInterface,
  ApprovedModelType
} from "@ukde/contracts";

import { createApprovedModel } from "../../../../lib/model-assignments";

function redirectTo(path: string, status = 303): NextResponse {
  return new NextResponse(null, {
    status,
    headers: { Location: path }
  });
}

function isModelType(value: string): value is ApprovedModelType {
  return value === "VLM" || value === "LLM" || value === "HTR";
}

function isModelRole(value: string): value is ApprovedModelRole {
  return (
    value === "TRANSCRIPTION_PRIMARY" ||
    value === "TRANSCRIPTION_FALLBACK" ||
    value === "ASSIST"
  );
}

function isServingInterface(value: string): value is ApprovedModelServingInterface {
  return (
    value === "OPENAI_CHAT" ||
    value === "OPENAI_EMBEDDING" ||
    value === "ENGINE_NATIVE" ||
    value === "RULES_NATIVE"
  );
}

function readRequiredText(formData: FormData, key: string): string | null {
  const raw = formData.get(key);
  if (typeof raw !== "string") {
    return null;
  }
  const normalized = raw.trim();
  return normalized.length > 0 ? normalized : null;
}

export async function POST(request: NextRequest) {
  const formData = await request.formData();

  const modelType = readRequiredText(formData, "model_type");
  const modelRole = readRequiredText(formData, "model_role");
  const modelFamily = readRequiredText(formData, "model_family");
  const modelVersion = readRequiredText(formData, "model_version");
  const servingInterface = readRequiredText(formData, "serving_interface");
  const engineFamily = readRequiredText(formData, "engine_family");
  const deploymentUnit = readRequiredText(formData, "deployment_unit");
  const artifactSubpath = readRequiredText(formData, "artifact_subpath");
  const checksumSha256 = readRequiredText(formData, "checksum_sha256");
  const runtimeProfile = readRequiredText(formData, "runtime_profile");
  const responseContractVersion = readRequiredText(
    formData,
    "response_contract_version"
  );

  if (
    !modelType ||
    !modelRole ||
    !modelFamily ||
    !modelVersion ||
    !servingInterface ||
    !engineFamily ||
    !deploymentUnit ||
    !artifactSubpath ||
    !checksumSha256 ||
    !runtimeProfile ||
    !responseContractVersion ||
    !isModelType(modelType) ||
    !isModelRole(modelRole) ||
    !isServingInterface(servingInterface)
  ) {
    return redirectTo("/approved-models?status=create-failed");
  }

  const result = await createApprovedModel({
    modelType,
    modelRole,
    modelFamily,
    modelVersion,
    servingInterface,
    engineFamily,
    deploymentUnit,
    artifactSubpath,
    checksumSha256,
    runtimeProfile,
    responseContractVersion
  });

  if (!result.ok) {
    return redirectTo("/approved-models?status=create-failed");
  }
  return redirectTo("/approved-models?status=created");
}
