/// <reference types="node" />
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Token-contract + accessibility guard for the Material 3 Expressive foundation.
 * Reads index.css directly and asserts that both themes define the required
 * design tokens, and that key text/fill pairings meet WCAG contrast minimums.
 * This locks the design-system contract so later refactors cannot silently
 * drop a role token or regress color accessibility.
 */

const css: string = readFileSync(resolve(process.cwd(), "src/index.css"), "utf8");

function block(marker: string): string {
  const start = css.indexOf(marker);
  if (start === -1) throw new Error(`marker not found: ${marker}`);
  const end = css.indexOf("}", start);
  return css.slice(start, end);
}

const darkBlock = block("color-scheme: dark;");
const lightBlock = block("color-scheme: light;");

function hex(scope: string, token: string): string {
  const match = new RegExp(`${token}:\\s*(#[0-9a-fA-F]{6})`).exec(scope);
  const value = match?.[1];
  if (!value) throw new Error(`token ${token} (solid hex) not found in scope`);
  return value;
}

function luminance(h: string): number {
  const channel = (offset: number): number => {
    const v = parseInt(h.slice(offset, offset + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  const r = channel(1);
  const g = channel(3);
  const b = channel(5);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  const hi = Math.max(la, lb);
  const lo = Math.min(la, lb);
  return (hi + 0.05) / (lo + 0.05);
}

const REQUIRED_ROLE_TOKENS = [
  "--primary", "--on-primary", "--primary-container", "--on-primary-container",
  "--secondary", "--on-secondary", "--secondary-container", "--on-secondary-container",
  "--tertiary", "--on-tertiary", "--tertiary-container", "--on-tertiary-container",
  "--surface-container", "--surface-container-high", "--surface-container-highest",
  "--outline", "--outline-variant",
];

const SHAPE_TOKENS = ["--shape-xs", "--shape-sm", "--shape-md", "--shape-lg", "--shape-xl", "--shape-full"];
const MOTION_TOKENS = ["--ease-standard", "--ease-emphasized", "--ease-spring", "--dur-short", "--dur-medium", "--dur-long"];

describe("M3 token foundation", () => {
  it("defines every color role in both themes", () => {
    for (const t of REQUIRED_ROLE_TOKENS) {
      expect(darkBlock, `dark missing ${t}`).toContain(`${t}:`);
      expect(lightBlock, `light missing ${t}`).toContain(`${t}:`);
    }
  });

  it("defines the expressive shape scale and motion tokens once", () => {
    for (const t of [...SHAPE_TOKENS, ...MOTION_TOKENS]) {
      expect(css, `missing ${t}`).toContain(`${t}:`);
    }
  });

  it("preserves the categorical chart palette (--series-1..8)", () => {
    for (let i = 1; i <= 8; i += 1) {
      expect(darkBlock).toContain(`--series-${i}:`);
      expect(lightBlock).toContain(`--series-${i}:`);
    }
  });

  it.each([
    ["dark", darkBlock],
    ["light", lightBlock],
  ])("%s theme meets WCAG contrast on key pairings", (_name, scope) => {
    // Body text on background and surface: >= 4.5:1 (normal text).
    expect(contrast(hex(scope, "--ink"), hex(scope, "--page"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(hex(scope, "--ink"), hex(scope, "--surface"))).toBeGreaterThanOrEqual(4.5);
    // On-color text over its filled role color: >= 4.5:1.
    expect(contrast(hex(scope, "--on-primary"), hex(scope, "--primary"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(hex(scope, "--on-secondary"), hex(scope, "--secondary"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(hex(scope, "--on-tertiary"), hex(scope, "--tertiary"))).toBeGreaterThanOrEqual(4.5);
    // Text over container roles: >= 4.5:1.
    expect(contrast(hex(scope, "--on-primary-container"), hex(scope, "--primary-container"))).toBeGreaterThanOrEqual(4.5);
  });
});
