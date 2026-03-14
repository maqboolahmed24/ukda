export type DocumentPageImageVariant =
  | "full"
  | "thumb"
  | "preprocessed_gray"
  | "preprocessed_bin";

export function projectDocumentPageImagePath(
  projectId: string,
  documentId: string,
  pageId: string,
  variant: DocumentPageImageVariant,
  options?: { runId?: string | null }
): string {
  const params = new URLSearchParams({ variant });
  if (options?.runId && options.runId.trim().length > 0) {
    params.set("runId", options.runId.trim());
  }
  return `/projects/${encodeURIComponent(projectId)}/documents/${encodeURIComponent(documentId)}/pages/${encodeURIComponent(pageId)}/image?${params.toString()}`;
}
