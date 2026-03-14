export const phase1PerformanceBudgetsMs = {
  documentLibraryInitialRender: 4000,
  documentLibraryFilterApply: 1500,
  viewerFirstPageRender: 3500,
  viewerThumbnailStripReady: 3000,
  uploadWizardFileSelection: 1000
} as const;

export function assertWithinBudget(
  metricName: string,
  durationMs: number,
  budgetMs: number
): void {
  if (durationMs > budgetMs) {
    throw new Error(
      `${metricName} exceeded budget (${durationMs}ms > ${budgetMs}ms).`
    );
  }
}
