import assert from "node:assert/strict";
import test from "node:test";

import { resolveSystemKey } from "../src/modules/keyboard/systemKeys.ts";
import { getVariantLabel } from "../src/modules/keyboard/layoutLabels.ts";

const keyAt = (
  row: number,
  column: number,
  key?: string,
): HTMLElement => ({
  dataset: {
    key,
    keyCol: column.toString(),
    keyRow: row.toString(),
  },
}) as HTMLElement;

test("left Shift remains native without a system modifier", () => {
  assert.equal(resolveSystemKey(keyAt(3, 0), false, false), undefined);
});

test("left Shift completes a system modifier chord", () => {
  assert.equal(
    resolveSystemKey(keyAt(3, 0), false, true),
    "KEY_LEFTSHIFT",
  );
});

test("existing system-key mappings are preserved", () => {
  assert.equal(resolveSystemKey(keyAt(0, 0), false, false), "KEY_ESC");
  assert.equal(resolveSystemKey(keyAt(0, 1), true, false), "KEY_F1");
  assert.equal(resolveSystemKey(keyAt(2, 1), false, true), "KEY_A");
});

test("keyboard layouts expose normal and Shift symbols", () => {
  const russianNumber = ["3", "№"];
  assert.equal(getVariantLabel(russianNumber, 0), "3");
  assert.equal(getVariantLabel(russianNumber, 1), "№");
});

test("keyboard layouts keep AltGr separate from Shift", () => {
  const spanishNumber = ["2", "\"", "@"];
  assert.equal(getVariantLabel(spanishNumber, 0), "2");
  assert.equal(getVariantLabel(spanishNumber, 1), "\"");
  assert.equal(getVariantLabel(spanishNumber, 2), "@");
});
