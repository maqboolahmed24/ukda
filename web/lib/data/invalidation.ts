import { revalidatePath } from "next/cache";

import type { MutationRuleContext, MutationRuleId } from "./mutation-rules";
import { resolveMutationRevalidationPaths } from "./mutation-rules";

export function revalidateAfterMutation(
  mutationId: MutationRuleId,
  context: MutationRuleContext = {}
): void {
  const targets = resolveMutationRevalidationPaths(mutationId, context);
  const deduped = new Set(targets);
  for (const path of deduped) {
    revalidatePath(path);
  }
}

