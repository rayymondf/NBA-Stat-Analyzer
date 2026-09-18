import { describe, expect, it } from "vitest";
import { num, ordinal, pct, signed, teamLogo } from "./format";

describe("format helpers", () => {
  it("formats nullable numbers consistently", () => {
    expect(num(null)).toBe("–");
    expect(num(12.345, 2)).toBe("12.35");
    expect(pct(0.612)).toBe("61.2%");
    expect(signed(4.2)).toBe("+4.2");
    expect(signed(-2)).toBe("-2.0");
  });

  it("formats ordinals and stable logo URLs", () => {
    expect(ordinal(1)).toBe("1st");
    expect(ordinal(12)).toBe("12th");
    expect(ordinal(23)).toBe("23rd");
    expect(teamLogo(1610612761)).toContain("1610612761");
  });
});

