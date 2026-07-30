import assert from "node:assert/strict";
import test from "node:test";

import {
  resolveVisualKeyLabels,
} from "../src/modules/keyboard/visualKeyLabels.ts";
import {
  selectSecondaryLabel,
} from "../src/modules/keyboard/layoutLabels.ts";

test("visual swap reverses labels without changing their positional mapping", () => {
  assert.deepEqual(resolveVisualKeyLabels("q", "α", false), {
    primary: "q",
    secondary: "α",
  });
  assert.deepEqual(resolveVisualKeyLabels("q", "α", true), {
    primary: "α",
    secondary: "q",
  });
});

test("identical and missing secondary labels are not decorated", () => {
  assert.deepEqual(resolveVisualKeyLabels("Q", "q", true), {
    primary: "Q",
  });
  assert.deepEqual(resolveVisualKeyLabels("q", undefined, true), {
    primary: "q",
  });
});

test("number row does not duplicate symbols already drawn by Steam", () => {
  assert.deepEqual(resolveVisualKeyLabels("=", "+", false, ["+", "="]), {
    primary: "=",
  });
  assert.deepEqual(resolveVisualKeyLabels("7", "?", false, ["&", "7"]), {
    primary: "7",
    secondary: "?",
  });
});

test("number row shows the secondary layout's Shift symbol without Shift", () => {
  assert.equal(selectSecondaryLabel("7", "?", 0, false), "?");
  assert.equal(selectSecondaryLabel("7", "?", 0, true), "?");
  assert.equal(selectSecondaryLabel("й", "Й", 1, false), "й");
  assert.equal(selectSecondaryLabel("й", "Й", 1, true), "Й");
});
