import assert from "node:assert/strict";
import test from "node:test";

import {
  resolveVisualKeyLabels,
} from "../src/modules/keyboard/visualKeyLabels.ts";

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
