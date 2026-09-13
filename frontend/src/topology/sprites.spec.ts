import { describe, expect, it } from "vitest";
import { SPRITE_CLASSES, SPRITE_FALLBACK, spriteFor } from "./types";

describe("spriteFor", () => {
  it("resolves all 9 classes to sprite-<cls>", () => {
    expect(SPRITE_CLASSES).toHaveLength(9);
    for (const cls of SPRITE_CLASSES) {
      expect(spriteFor(cls)).toBe(`sprite-${cls}`);
    }
  });

  it("falls back on unknown class", () => {
    expect(spriteFor("bogus")).toBe(SPRITE_FALLBACK);
    expect(spriteFor("")).toBe(SPRITE_FALLBACK);
  });
});
