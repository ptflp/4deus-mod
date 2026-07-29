import assert from "node:assert/strict";
import test from "node:test";

import { isVirtualKeyboardVisible } from
  "../src/modules/keyboard/keyboardVisibility.ts";

test("Steam visibility is authoritative when available", () => {
  assert.equal(
    isVirtualKeyboardVisible({
      IsShowingVirtualKeyboard: { Value: true },
    }, false),
    true,
  );
  assert.equal(
    isVirtualKeyboardVisible({
      IsShowingVirtualKeyboard: { Value: false },
    }, true),
    false,
  );
});

test("keyboard DOM presence is used on older Steam clients", () => {
  assert.equal(isVirtualKeyboardVisible(undefined, true), true);
  assert.equal(isVirtualKeyboardVisible(undefined, false), false);
});
