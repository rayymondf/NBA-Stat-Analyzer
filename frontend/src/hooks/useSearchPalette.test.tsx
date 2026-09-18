import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useSearchPalette } from "./useSearchPalette";

describe("useSearchPalette", () => {
  it("opens with Ctrl+K and closes with Escape", () => {
    const { result } = renderHook(() => useSearchPalette());
    expect(result.current.open).toBe(false);

    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true })));
    expect(result.current.open).toBe(true);

    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })));
    expect(result.current.open).toBe(false);
  });
});

