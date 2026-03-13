import { describe, expect, it } from "vitest";

import {
  findFirstEnabledIndex,
  findNextEnabledIndex,
  paginateRows,
  resolveToolbarTargetIndex,
  stableSortRows
} from "./primitives-logic";

describe("primitive interaction logic", () => {
  it("resolves first and next enabled toolbar targets", () => {
    const disabled = [false, true, false, false];
    expect(findFirstEnabledIndex(disabled)).toBe(0);
    expect(findNextEnabledIndex(disabled, 0, 1)).toBe(2);
    expect(findNextEnabledIndex(disabled, 2, 1)).toBe(3);
    expect(findNextEnabledIndex(disabled, 3, 1)).toBe(0);
    expect(findNextEnabledIndex(disabled, 0, -1)).toBe(3);
  });

  it("resolves toolbar arrow/home/end keyboard navigation", () => {
    const disabled = [true, false, false, true, false];
    expect(resolveToolbarTargetIndex("Home", disabled, 2)).toBe(1);
    expect(resolveToolbarTargetIndex("End", disabled, 2)).toBe(4);
    expect(resolveToolbarTargetIndex("ArrowRight", disabled, 1)).toBe(2);
    expect(resolveToolbarTargetIndex("ArrowLeft", disabled, 1)).toBe(4);
  });

  it("keeps table sorting stable for equal values", () => {
    const rows = [
      { id: "a", value: 2 },
      { id: "b", value: 1 },
      { id: "c", value: 2 }
    ];
    const asc = stableSortRows(rows, (row) => row.value, "asc");
    expect(asc.map((row) => row.id)).toEqual(["b", "a", "c"]);
    const desc = stableSortRows(rows, (row) => row.value, "desc");
    expect(desc.map((row) => row.id)).toEqual(["a", "c", "b"]);
  });

  it("paginates row slices deterministically", () => {
    const rows = Array.from({ length: 9 }, (_, index) => index + 1);
    expect(paginateRows(rows, 4, 0)).toEqual([1, 2, 3, 4]);
    expect(paginateRows(rows, 4, 1)).toEqual([5, 6, 7, 8]);
    expect(paginateRows(rows, 4, 2)).toEqual([9]);
    expect(paginateRows(rows, 4, -1)).toEqual([1, 2, 3, 4]);
  });
});
