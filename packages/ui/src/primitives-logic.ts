export type SortDirection = "asc" | "desc";

export interface SortState {
  key: string;
  direction: SortDirection;
}

export function findFirstEnabledIndex(disabledStates: boolean[]): number {
  return disabledStates.findIndex((disabled) => !disabled);
}

export function findNextEnabledIndex(
  disabledStates: boolean[],
  startIndex: number,
  direction: 1 | -1
): number {
  if (disabledStates.length === 0) {
    return -1;
  }
  const enabledCount = disabledStates.filter((disabled) => !disabled).length;
  if (enabledCount === 0) {
    return -1;
  }
  let index = startIndex;
  for (let step = 0; step < disabledStates.length; step += 1) {
    index =
      (index + direction + disabledStates.length) % disabledStates.length;
    if (!disabledStates[index]) {
      return index;
    }
  }
  return -1;
}

export function resolveToolbarTargetIndex(
  key: "ArrowLeft" | "ArrowRight" | "Home" | "End",
  disabledStates: boolean[],
  activeIndex: number
): number {
  if (disabledStates.length === 0) {
    return -1;
  }
  if (key === "Home") {
    return findFirstEnabledIndex(disabledStates);
  }
  if (key === "End") {
    for (let index = disabledStates.length - 1; index >= 0; index -= 1) {
      if (!disabledStates[index]) {
        return index;
      }
    }
    return -1;
  }
  return findNextEnabledIndex(
    disabledStates,
    activeIndex,
    key === "ArrowRight" ? 1 : -1
  );
}

export function stableSortRows<T>(
  rows: T[],
  getValue: (row: T) => string | number,
  direction: SortDirection
): T[] {
  return rows
    .map((row, index) => ({ index, row }))
    .sort((left, right) => {
      const leftValue = getValue(left.row);
      const rightValue = getValue(right.row);
      if (leftValue < rightValue) {
        return direction === "asc" ? -1 : 1;
      }
      if (leftValue > rightValue) {
        return direction === "asc" ? 1 : -1;
      }
      return left.index - right.index;
    })
    .map(({ row }) => row);
}

export function paginateRows<T>(
  rows: T[],
  pageSize: number,
  pageIndex: number
): T[] {
  const normalizedPage = Math.max(pageIndex, 0);
  const normalizedPageSize = Math.max(pageSize, 1);
  const start = normalizedPage * normalizedPageSize;
  return rows.slice(start, start + normalizedPageSize);
}
