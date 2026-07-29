import type {
  DeckButton,
  DeckButtonAction,
  DeckButtonBindings,
  DeckQuickActions,
} from "../../core/settings";

export const DECK_BUTTONS: ReadonlyArray<{
  button: DeckButton;
  code: number;
  label: string;
}> = [
  { button: "view", code: 13, label: "View" },
  { button: "l1", code: 5, label: "L1" },
  { button: "r1", code: 6, label: "R1" },
  { button: "l2", code: 7, label: "L2" },
  { button: "r2", code: 8, label: "R2" },
  { button: "l3", code: 15, label: "L3" },
  { button: "r3", code: 16, label: "R3" },
  { button: "l4", code: 23, label: "L4" },
  { button: "r4", code: 25, label: "R4" },
  { button: "l5", code: 24, label: "L5" },
  { button: "r5", code: 26, label: "R5" },
];

const BUTTON_BY_CODE = new Map(
  DECK_BUTTONS.map(({ button, code }) => [code, button]),
);

export interface DeckQuickChord {
  keyName: string;
  label: string;
  withAlt: boolean;
  withControl: boolean;
  withShift: boolean;
}

export interface DeckQuickKeyOption {
  keyName: string;
  label: string;
  token?: string;
}

export const DECK_QUICK_KEY_GROUPS: ReadonlyArray<{
  label: string;
  options: readonly DeckQuickKeyOption[];
}> = [
  {
    label: "System",
    options: [
      ["KEY_ESC", "Esc"],
      ["KEY_SPACE", "Space"],
      ["KEY_BACKSPACE", "Backspace"],
      ["KEY_ENTER", "Enter"],
      ["KEY_TAB", "Tab"],
      ["KEY_DELETE", "Delete"],
      ["KEY_INSERT", "Insert"],
      ["KEY_HOME", "Home"],
      ["KEY_END", "End"],
      ["KEY_PAGEUP", "PageUp"],
      ["KEY_PAGEDOWN", "PageDown"],
      ["KEY_UP", "↑"],
      ["KEY_DOWN", "↓"],
      ["KEY_LEFT", "←"],
      ["KEY_RIGHT", "→"],
      ["KEY_MINUS", "Minus"],
      ["KEY_EQUAL", "Equal"],
      ["KEY_COMMA", "Comma"],
      ["KEY_DOT", "Dot"],
      ["KEY_SLASH", "Slash"],
      ["KEY_BACKSLASH", "Backslash"],
      ["KEY_SEMICOLON", "Semicolon"],
      ["KEY_APOSTROPHE", "Apostrophe"],
      ["KEY_GRAVE", "Grave"],
    ].map((option) => Array.isArray(option)
      ? { keyName: option[0], label: option[1] }
      : option),
  },
  {
    label: "F1–F12",
    options: Array.from({ length: 12 }, (_, index) => ({
      keyName: `KEY_F${index + 1}`,
      label: `F${index + 1}`,
    })),
  },
  {
    label: "0–9",
    options: Array.from({ length: 10 }, (_, index) => ({
      keyName: `KEY_${index}`,
      label: index.toString(),
    })),
  },
  {
    label: "A–Z",
    options: Array.from({ length: 26 }, (_, index) => {
      const label = String.fromCharCode("A".charCodeAt(0) + index);
      return { keyName: `KEY_${label}`, label };
    }),
  },
];

const QUICK_KEY_BY_NAME = new Map(
  DECK_QUICK_KEY_GROUPS.flatMap(({ options }) =>
    options.map((option) => [option.keyName, option])),
);

const KEY_ALIASES: Record<string, readonly [keyName: string, label: string]> = {
  ESC: ["KEY_ESC", "Esc"],
  ESCAPE: ["KEY_ESC", "Esc"],
  SPACE: ["KEY_SPACE", "Space"],
  BACKSPACE: ["KEY_BACKSPACE", "Backspace"],
  ENTER: ["KEY_ENTER", "Enter"],
  RETURN: ["KEY_ENTER", "Enter"],
  TAB: ["KEY_TAB", "Tab"],
  DELETE: ["KEY_DELETE", "Delete"],
  DEL: ["KEY_DELETE", "Delete"],
  INSERT: ["KEY_INSERT", "Insert"],
  INS: ["KEY_INSERT", "Insert"],
  HOME: ["KEY_HOME", "Home"],
  END: ["KEY_END", "End"],
  PAGEUP: ["KEY_PAGEUP", "PageUp"],
  PGUP: ["KEY_PAGEUP", "PageUp"],
  PAGEDOWN: ["KEY_PAGEDOWN", "PageDown"],
  PGDN: ["KEY_PAGEDOWN", "PageDown"],
  UP: ["KEY_UP", "Up"],
  DOWN: ["KEY_DOWN", "Down"],
  LEFT: ["KEY_LEFT", "Left"],
  RIGHT: ["KEY_RIGHT", "Right"],
  MINUS: ["KEY_MINUS", "Minus"],
  EQUAL: ["KEY_EQUAL", "Equal"],
  COMMA: ["KEY_COMMA", "Comma"],
  DOT: ["KEY_DOT", "Dot"],
  PERIOD: ["KEY_DOT", "Dot"],
  SLASH: ["KEY_SLASH", "Slash"],
  BACKSLASH: ["KEY_BACKSLASH", "Backslash"],
  SEMICOLON: ["KEY_SEMICOLON", "Semicolon"],
  APOSTROPHE: ["KEY_APOSTROPHE", "Apostrophe"],
  QUOTE: ["KEY_APOSTROPHE", "Apostrophe"],
  GRAVE: ["KEY_GRAVE", "Grave"],
  LEFTCTRL: ["KEY_LEFTCTRL", "Ctrl"],
  LEFTALT: ["KEY_LEFTALT", "Alt"],
  LEFTSHIFT: ["KEY_LEFTSHIFT", "Shift"],
};

const resolveQuickKey = (
  token: string,
): readonly [keyName: string, label: string] | undefined => {
  const normalized = token.toUpperCase();
  if (/^[A-Z]$/u.test(normalized))
    return [`KEY_${normalized}`, normalized];
  if (/^[0-9]$/u.test(normalized))
    return [`KEY_${normalized}`, normalized];
  if (/^F(?:[1-9]|1[0-2])$/u.test(normalized))
    return [`KEY_${normalized}`, normalized];
  return KEY_ALIASES[normalized];
};

interface QuickChordModifiers {
  withAlt: boolean;
  withControl: boolean;
  withShift: boolean;
}

const MODIFIER_PROPERTIES: Record<
  string,
  keyof QuickChordModifiers
> = {
  ALT: "withAlt",
  CONTROL: "withControl",
  CTRL: "withControl",
  SHIFT: "withShift",
};

const parseQuickChordParts = (
  tokens: string[],
): {
  key: readonly [keyName: string, label: string];
  modifiers: QuickChordModifiers;
} | undefined => {
  const modifiers: QuickChordModifiers = {
    withAlt: false,
    withControl: false,
    withShift: false,
  };
  let key: readonly [keyName: string, label: string] | undefined;
  for (const token of tokens) {
    const normalized = token.toUpperCase();
    const modifier = MODIFIER_PROPERTIES[normalized];
    if (modifier) {
      modifiers[modifier] = true;
      continue;
    }
    const resolvedKey = resolveQuickKey(normalized);
    if (!resolvedKey || key)
      return undefined;
    key = resolvedKey;
  }
  if (!key)
    return undefined;
  return { key, modifiers };
};

export const parseDeckQuickChord = (
  value: string,
): DeckQuickChord | undefined => {
  const tokens = value.split("+").map((token) => token.trim())
    .filter(Boolean);
  const parts = parseQuickChordParts(tokens);
  if (!parts)
    return undefined;
  const { key, modifiers } = parts;
  const labels = [
    modifiers.withControl ? "Ctrl" : undefined,
    modifiers.withAlt ? "Alt" : undefined,
    modifiers.withShift ? "Shift" : undefined,
    key[1],
  ].filter((label) => label !== undefined);
  return {
    keyName: key[0],
    label: labels.join(" + "),
    ...modifiers,
  };
};

export const formatDeckQuickChord = (
  keyName: string,
  modifiers: Pick<
    DeckQuickChord,
    "withAlt" | "withControl" | "withShift"
  >,
): string => {
  const key = QUICK_KEY_BY_NAME.get(keyName);
  if (!key)
    return "";
  return [
    modifiers.withControl ? "Ctrl" : undefined,
    modifiers.withAlt ? "Alt" : undefined,
    modifiers.withShift ? "Shift" : undefined,
    key.token ?? key.label,
  ].filter((part) => part !== undefined).join("+");
};

export type DeckButtonCommand =
  | { action: DeckButtonAction; kind: "key" }
  | { chord: DeckQuickChord; kind: "chord" };

export const resolveDeckButtonAction = (
  bindings: DeckButtonBindings,
  buttonCode: number,
): DeckButtonAction | undefined => {
  const button = BUTTON_BY_CODE.get(buttonCode);
  if (!button)
    return undefined;
  const action = bindings[button];
  return action === "none" ? undefined : action;
};

export const resolveDeckButtonCommand = (
  bindings: DeckButtonBindings,
  quickActions: DeckQuickActions,
  buttonCode: number,
): DeckButtonCommand | undefined => {
  const button = BUTTON_BY_CODE.get(buttonCode);
  if (!button)
    return undefined;
  const chord = parseDeckQuickChord(quickActions[button]);
  if (chord) {
    return {
      chord,
      kind: "chord",
    };
  }
  const action = bindings[button];
  return action === "none" ? undefined : { action, kind: "key" };
};
