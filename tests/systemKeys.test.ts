import assert from "node:assert/strict";
import test from "node:test";

import {
  isKeyNameVisibleInLayer,
  isKeyboardHelpKey,
  isShiftKey,
  LANGUAGE_SWITCH_OPTIONS,
  languageSwitchModifiers,
  resolveLanguageSwitchOption,
  resolveSystemKey,
  shouldAutoSwapVisualLayer,
  VISUAL_SWAP_ACTION,
} from "../src/modules/keyboard/systemKeys.ts";
import {
  getVariantLabel,
  isSecondaryLabelRow,
  isVisualSwapRow,
} from "../src/modules/keyboard/layoutLabels.ts";
import {
  DECK_QUICK_KEY_GROUPS,
  formatDeckQuickChord,
  parseDeckQuickChord,
  resolveDeckButtonAction,
  resolveDeckButtonCommand,
} from "../src/modules/keyboard/deckButtonBindings.ts";
import type {
  DeckButtonBindings,
  DeckQuickActions,
} from "../src/core/settings.ts";

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
  assert.equal(isShiftKey(keyAt(3, 0)), true);
  assert.equal(isShiftKey(keyAt(3, 1)), false);
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

test("Fn turns the layout switch into Start", () => {
  assert.equal(
    resolveSystemKey(keyAt(4, 0, "SwitchKeys_Layout"), true, false),
    "KEY_LEFTMETA",
  );
  assert.equal(
    resolveSystemKey(keyAt(4, 0, "SwitchKeys_Layout"), false, false),
    undefined,
  );
});

test("language switching supports all configured system chords", () => {
  assert.deepEqual(languageSwitchModifiers("alt-shift"), {
    keyName: "KEY_LEFTSHIFT",
    withAlt: true,
    withControl: false,
    withMeta: false,
  });
  assert.deepEqual(languageSwitchModifiers("ctrl-shift"), {
    keyName: "KEY_LEFTSHIFT",
    withAlt: false,
    withControl: true,
    withMeta: false,
  });
  assert.deepEqual(languageSwitchModifiers("meta-space"), {
    keyName: "KEY_SPACE",
    withAlt: false,
    withControl: false,
    withMeta: true,
  });
});

test("visual auto-swap follows system shortcuts but not native Steam layouts", () => {
  assert.equal(shouldAutoSwapVisualLayer(false, "alt-shift"), false);
  assert.equal(shouldAutoSwapVisualLayer(true, "alt-shift"), true);
  assert.equal(shouldAutoSwapVisualLayer(true, "ctrl-shift"), true);
  assert.equal(shouldAutoSwapVisualLayer(true, "meta-space"), true);
  assert.equal(shouldAutoSwapVisualLayer(true, "native"), false);
});

test("language menu keeps four shortcuts plus an independent visual action", () => {
  assert.deepEqual(
    LANGUAGE_SWITCH_OPTIONS.map(({ row, column, value }) => ({
      row,
      column,
      value,
    })),
    [
      { row: 2, column: 3, value: "alt-shift" },
      { row: 3, column: 3, value: "ctrl-shift" },
      { row: 2, column: 8, value: "meta-space" },
      { row: 3, column: 8, value: "native" },
      { row: 4, column: 2, value: "swap" },
    ],
  );
  assert.equal(resolveLanguageSwitchOption(keyAt(2, 3))?.value, "alt-shift");
  assert.equal(resolveLanguageSwitchOption(keyAt(3, 8))?.value, "native");
  assert.equal(
    resolveLanguageSwitchOption(keyAt(4, 2))?.value,
    VISUAL_SWAP_ACTION,
  );
  assert.equal(resolveLanguageSwitchOption(keyAt(2, 4)), undefined);
});

test("the lower-right slash key owns the keyboard help action", () => {
  assert.equal(isKeyboardHelpKey(keyAt(3, 10, "/")), true);
  assert.equal(isKeyboardHelpKey(keyAt(3, 9, ".")), false);
});

test("bound-key visuals follow the keyboard's visible layer", () => {
  assert.equal(isKeyNameVisibleInLayer("KEY_A", false, false), true);
  assert.equal(isKeyNameVisibleInLayer("KEY_LEFTSHIFT", false, false), true);
  assert.equal(isKeyNameVisibleInLayer("KEY_ESC", false, false), false);
  assert.equal(isKeyNameVisibleInLayer("KEY_ESC", true, false), true);
  assert.equal(isKeyNameVisibleInLayer("KEY_LEFTCTRL", false, false), false);
  assert.equal(isKeyNameVisibleInLayer("KEY_LEFTCTRL", true, false), true);
  assert.equal(isKeyNameVisibleInLayer("KEY_GRAVE", false, false), true);
  assert.equal(isKeyNameVisibleInLayer("KEY_GRAVE", true, false), false);
  assert.equal(isKeyNameVisibleInLayer("KEY_1", true, false), true);
  assert.equal(isKeyNameVisibleInLayer("KEY_1", true, true), false);
  assert.equal(isKeyNameVisibleInLayer("KEY_F1", true, false), false);
  assert.equal(isKeyNameVisibleInLayer("KEY_F1", true, true), true);
  assert.equal(isKeyNameVisibleInLayer("KEY_BACKSPACE", true, true), false);
  assert.equal(isKeyNameVisibleInLayer("KEY_DELETE", true, true), true);
});

test("Steam Deck shoulder, trigger, stick, and rear codes resolve keys", () => {
  const bindings: DeckButtonBindings = {
    view: "none",
    l1: "KEY_ESC",
    r1: "KEY_SPACE",
    l2: "KEY_BACKSPACE",
    r2: "KEY_ENTER",
    l3: "KEY_HOME",
    r3: "KEY_END",
    l4: "KEY_TAB",
    r4: "KEY_LEFTALT",
    l5: "KEY_LEFTSHIFT",
    r5: "KEY_LEFTCTRL",
  };
  assert.equal(resolveDeckButtonAction(bindings, 5), "KEY_ESC");
  assert.equal(resolveDeckButtonAction(bindings, 6), "KEY_SPACE");
  assert.equal(resolveDeckButtonAction(bindings, 7), "KEY_BACKSPACE");
  assert.equal(resolveDeckButtonAction(bindings, 8), "KEY_ENTER");
  assert.equal(resolveDeckButtonAction(bindings, 15), "KEY_HOME");
  assert.equal(resolveDeckButtonAction(bindings, 16), "KEY_END");
  assert.equal(resolveDeckButtonAction(bindings, 23), "KEY_TAB");
  assert.equal(resolveDeckButtonAction(bindings, 25), "KEY_LEFTALT");
  assert.equal(resolveDeckButtonAction(bindings, 24), "KEY_LEFTSHIFT");
  assert.equal(resolveDeckButtonAction(bindings, 26), "KEY_LEFTCTRL");
  assert.equal(resolveDeckButtonAction(bindings, 13), undefined);
  assert.equal(resolveDeckButtonAction(bindings, 1), undefined);
});

test("quick actions take priority over regular button bindings", () => {
  const bindings: DeckButtonBindings = {
    view: "KEY_TAB",
    l1: "KEY_ESC",
    r1: "none",
    l2: "none",
    r2: "KEY_ENTER",
    l3: "none",
    r3: "none",
    l4: "KEY_LEFTCTRL",
    r4: "KEY_LEFTSHIFT",
    l5: "none",
    r5: "none",
  };
  const quickActions: DeckQuickActions = {
    view: "M",
    l1: "none",
    r1: "none",
    l2: "none",
    r2: "Ctrl+Enter",
    l3: "none",
    r3: "none",
    l4: "Ctrl+Shift+Delete",
    r4: "none",
    l5: "none",
    r5: "none",
  };
  assert.deepEqual(resolveDeckButtonCommand(bindings, quickActions, 23), {
    chord: {
      keyName: "KEY_DELETE",
      label: "Ctrl + Shift + Delete",
      withAlt: false,
      withControl: true,
      withShift: true,
    },
    kind: "chord",
  });
  assert.deepEqual(resolveDeckButtonCommand(bindings, quickActions, 5), {
    action: "KEY_ESC",
    kind: "key",
  });
  assert.deepEqual(resolveDeckButtonCommand(bindings, quickActions, 8), {
    chord: {
      keyName: "KEY_ENTER",
      label: "Ctrl + Enter",
      withAlt: false,
      withControl: true,
      withShift: false,
    },
    kind: "chord",
  });
  assert.deepEqual(resolveDeckButtonCommand(bindings, quickActions, 13), {
    chord: {
      keyName: "KEY_M",
      label: "M",
      withAlt: false,
      withControl: false,
      withShift: false,
    },
    kind: "chord",
  });
});

test("custom quick chords parse supported keys and reject invalid input", () => {
  assert.deepEqual(parseDeckQuickChord(" alt + ctrl + F12 "), {
    keyName: "KEY_F12",
    label: "Ctrl + Alt + F12",
    withAlt: true,
    withControl: true,
    withShift: false,
  });
  assert.deepEqual(parseDeckQuickChord("Ctrl+Shift+PageDown"), {
    keyName: "KEY_PAGEDOWN",
    label: "Ctrl + Shift + PageDown",
    withAlt: false,
    withControl: true,
    withShift: true,
  });
  assert.deepEqual(parseDeckQuickChord("Alt+Esc"), {
    keyName: "KEY_ESC",
    label: "Alt + Esc",
    withAlt: true,
    withControl: false,
    withShift: false,
  });
  assert.deepEqual(parseDeckQuickChord("Ctrl+K"), {
    keyName: "KEY_K",
    label: "Ctrl + K",
    withAlt: false,
    withControl: true,
    withShift: false,
  });
  assert.equal(parseDeckQuickChord("Ctrl+NotAKey"), undefined);
  assert.equal(parseDeckQuickChord("Ctrl+W+Delete"), undefined);
});

test("quick-action selector exposes grouped keys and formats chords", () => {
  assert.deepEqual(
    DECK_QUICK_KEY_GROUPS.map((group) => group.label),
    ["System", "F1–F12", "0–9", "A–Z"],
  );
  assert.equal(
    formatDeckQuickChord("KEY_DELETE", {
      withAlt: false,
      withControl: true,
      withShift: true,
    }),
    "Ctrl+Shift+Delete",
  );
  assert.equal(
    formatDeckQuickChord("KEY_W", {
      withAlt: true,
      withControl: true,
      withShift: false,
    }),
    "Ctrl+Alt+W",
  );
  assert.deepEqual(parseDeckQuickChord("LeftAlt"), {
    keyName: "KEY_LEFTALT",
    label: "Alt",
    withAlt: false,
    withControl: false,
    withShift: false,
  });
});

test("keyboard layouts expose normal and Shift symbols", () => {
  const shiftedNumber = ["3", "#"];
  assert.equal(getVariantLabel(shiftedNumber, 0), "3");
  assert.equal(getVariantLabel(shiftedNumber, 1), "#");
});

test("keyboard layouts keep AltGr separate from Shift", () => {
  const altGrNumber = ["2", "\"", "@"];
  assert.equal(getVariantLabel(altGrNumber, 0), "2");
  assert.equal(getVariantLabel(altGrNumber, 1), "\"");
  assert.equal(getVariantLabel(altGrNumber, 2), "@");
});

test("number labels remain visible but stay outside visual swapping", () => {
  assert.equal(isSecondaryLabelRow(0), true);
  assert.equal(isSecondaryLabelRow(1), true);
  assert.equal(isSecondaryLabelRow(2), true);
  assert.equal(isSecondaryLabelRow(3), true);
  assert.equal(isSecondaryLabelRow(4), false);
  assert.equal(isVisualSwapRow(0), false);
  assert.equal(isVisualSwapRow(1), true);
  assert.equal(isVisualSwapRow(2), true);
  assert.equal(isVisualSwapRow(3), true);
  assert.equal(isVisualSwapRow(4), false);
});
