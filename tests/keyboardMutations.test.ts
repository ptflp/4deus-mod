import assert from "node:assert/strict";
import test from "node:test";

import {
  normalizedNativeClasses,
} from "../src/modules/keyboard/keyboardMutations.ts";

test("mod-owned classes do not change the native class signature", () => {
  const before = "Panel Focusable";
  const after = [
    "Panel",
    "fourdeus-secondary-label-key",
    "Focusable",
    "fourdeus-system-key",
  ].join(" ");
  assert.equal(normalizedNativeClasses(before), "Panel Focusable");
  assert.equal(normalizedNativeClasses(after), "Panel Focusable");
});

test("native Steam class changes remain observable", () => {
  const before = normalizedNativeClasses("Panel Focusable");
  const after = normalizedNativeClasses("Panel Focusable SteamShiftActive");
  assert.notEqual(before, after);
});
