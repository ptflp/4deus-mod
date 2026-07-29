import assert from "node:assert/strict";
import test from "node:test";

import {
  isRelevantKeyClassChange,
  KEYBOARD_IDENTITY_ATTRIBUTES,
  normalizedNativeClasses,
  SHIFT_STATE_ATTRIBUTES,
} from "../src/modules/keyboard/keyboardMutations.ts";

test("regular keys are not observed for focus class churn", () => {
  assert.equal(KEYBOARD_IDENTITY_ATTRIBUTES.includes("class"), false);
  assert.deepEqual(SHIFT_STATE_ATTRIBUTES, ["class"]);
});

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

test("mod-owned Shift classes do not trigger a keyboard refresh", () => {
  assert.equal(
    isRelevantKeyClassChange(
      "Panel SteamShiftActive",
      "Panel SteamShiftActive fourdeus-secondary-label-key",
      true,
    ),
    false,
  );
});

test("only native Shift state changes trigger a class refresh", () => {
  assert.equal(
    isRelevantKeyClassChange("Panel", "Panel Focused", false),
    false,
  );
  assert.equal(
    isRelevantKeyClassChange("Panel", "Panel SteamShiftActive", true),
    true,
  );
});
