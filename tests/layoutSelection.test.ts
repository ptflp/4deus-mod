import assert from "node:assert/strict";
import test from "node:test";

import {
  activateQwertyLayout,
  type KeyboardLayoutController,
  shouldShowSecondaryLayer,
  selectSecondaryLayout,
} from "../src/modules/keyboard/layoutSelection.ts";

const layouts = [
  { layout: 0, name: "qwerty" },
  { layout: 5, name: "german" },
  { layout: 9, name: "greek" },
  { layout: 13, name: "japanese" },
];

test("explicit secondary layout works among four enabled layouts", () => {
  assert.equal(
    selectSecondaryLayout(layouts, "13", {
      currentLayout: 0,
      selectedLayouts: [0, 5, 9, 13],
    })?.layout,
    13,
  );
  assert.equal(
    selectSecondaryLayout(layouts, "13", {
      currentLayout: 13,
      selectedLayouts: [0, 5, 9, 13],
    })?.layout,
    0,
  );
});

test("automatic secondary layout follows arbitrary selected layout order", () => {
  assert.equal(
    selectSecondaryLayout(layouts, "auto", {
      currentLayout: 0,
      selectedLayouts: [0, 13, 5, 9],
    })?.layout,
    13,
  );
  assert.equal(
    selectSecondaryLayout(layouts, "auto", {
      currentLayout: 13,
      selectedLayouts: [0, 13, 5, 9],
    })?.layout,
    0,
  );
  assert.equal(
    selectSecondaryLayout(layouts, "auto", {
      currentLayout: 5,
      selectedLayouts: [0, 13, 5, 9],
    })?.layout,
    0,
  );
});

test("invalid or unavailable preferences fall back across every layout", () => {
  assert.equal(
    selectSecondaryLayout(layouts, "999", {
      currentLayout: 0,
      selectedLayouts: [0, 9, 13, 5],
    })?.layout,
    9,
  );
  assert.equal(
    selectSecondaryLayout(layouts, "auto", undefined)?.layout,
    0,
  );
});

test("secondary layout is unavailable when only the current layout exists", () => {
  assert.equal(
    selectSecondaryLayout([layouts[0]], "auto", {
      currentLayout: 0,
      selectedLayouts: [0],
    }),
    undefined,
  );
});

test("QWERTY-only mode hides the second layer on every other layout", () => {
  assert.equal(shouldShowSecondaryLayer(0, true), true);
  for (const layout of layouts.slice(1))
    assert.equal(shouldShowSecondaryLayer(layout.layout, true), false);
});

test("disabling QWERTY-only mode supports every layout without a pair limit", () => {
  for (const layout of layouts)
    assert.equal(shouldShowSecondaryLayer(layout.layout, false), true);
  assert.equal(shouldShowSecondaryLayer(undefined, false), true);
});

test("missing Steam layout state keeps the secondary layer available", () => {
  assert.equal(shouldShowSecondaryLayer(undefined, true), true);
});

test("custom shortcuts activate QWERTY directly among four layouts", () => {
  let currentLayout = 13;
  const activations: number[] = [];
  const controller: KeyboardLayoutController = {
    GetKeyboardLayoutSettings: () => ({
      currentLayout,
      selectedLayouts: [0, 5, 9, 13],
    }),
    SetKeyboardLayout: (layout) => {
      activations.push(layout);
      currentLayout = layout;
    },
  };

  assert.equal(activateQwertyLayout(controller), true);
  assert.deepEqual(activations, [0]);
  assert.equal(currentLayout, 0);

  assert.equal(activateQwertyLayout(controller), true);
  assert.deepEqual(activations, [0]);
});

test("QWERTY activation reports when Steam cannot select a layout directly", () => {
  assert.equal(activateQwertyLayout(undefined), false);
  assert.equal(
    activateQwertyLayout({
      GetKeyboardLayoutSettings: () => ({
        currentLayout: 9,
        selectedLayouts: [0, 5, 9, 13],
      }),
    }),
    false,
  );
});
