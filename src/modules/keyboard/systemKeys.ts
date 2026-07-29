import type { LanguageSwitchShortcut } from "../../core/settings";

export const EMOJI_KEY = "SwitchKeys_Steam";
export const LAYOUT_KEY = "SwitchKeys_Layout";
export const SYNTHETIC_FUNCTION_KEY = "4deus_Fn";
export const NATIVE_ALT_KEY = "AltGr";
export const SYNTHETIC_ALT_KEY = "4deus_Alt";
export const KEY_SELECTOR = "[data-key-row][data-key-col]";

export interface LanguageSwitchOption {
  column: number;
  label: string;
  row: number;
  value: LanguageSwitchShortcut;
}

export const LANGUAGE_SWITCH_OPTIONS: ReadonlyArray<LanguageSwitchOption> = [
  { row: 2, column: 3, label: "Alt\nShift", value: "alt-shift" },
  { row: 3, column: 3, label: "Ctrl\nShift", value: "ctrl-shift" },
  { row: 2, column: 8, label: "Cmd\nSpace", value: "meta-space" },
  { row: 3, column: 8, label: "Steam", value: "native" },
];

const LANGUAGE_SWITCH_OPTIONS_BY_POSITION = new Map(
  LANGUAGE_SWITCH_OPTIONS.map((option) => [
    `${option.row}:${option.column}`,
    option,
  ]),
);

const KEY_ROWS = [
  [
    "GRAVE", "1", "2", "3", "4", "5", "6",
    "7", "8", "9", "0", "MINUS", "EQUAL", "BACKSPACE",
  ],
  [
    "TAB", "Q", "W", "E", "R", "T", "Y",
    "U", "I", "O", "P", "LEFTBRACE", "RIGHTBRACE", "BACKSLASH",
  ],
  [
    null, "A", "S", "D", "F", "G", "H",
    "J", "K", "L", "SEMICOLON", "APOSTROPHE", "ENTER",
  ],
  [null, "Z", "X", "C", "V", "B", "N", "M", "COMMA", "DOT", "SLASH"],
  [null, null, "SPACE", null, "LEFT", "RIGHT"],
] as const;

const KEY_NAMES_BY_POSITION = Object.fromEntries(
  KEY_ROWS.flatMap((row, rowIndex) =>
    row.flatMap((name, columnIndex) =>
      name ? [[`${rowIndex}:${columnIndex}`, `KEY_${name}`]] : [],
    ),
  ),
) as Record<string, string>;

const DIRECT_SYSTEM_KEYS: Record<string, string> = {
  "0:0": "KEY_ESC",
};

const SYSTEM_KEYS_BY_NAME: Record<string, string> = {
  ArrowLeft: "KEY_LEFT",
  ArrowRight: "KEY_RIGHT",
};

const SYSTEM_KEYS_BY_POSITION: Record<string, string> = {
  // Steam's left Shift key has no stable data-key name.
  "3:0": "KEY_LEFTSHIFT",
};

const FUNCTION_KEYS: Record<string, string> = Object.fromEntries([
  ...Array.from(
    { length: 12 },
    (_, index) => [`0:${index + 1}`, `KEY_F${index + 1}`],
  ),
  ["0:13", "KEY_DELETE"],
]);

const FUNCTION_KEYS_BY_NAME: Record<string, string> = {
  [LAYOUT_KEY]: "KEY_LEFTMETA",
};

const POSITIONS_BY_KEY_NAME = new Map(
  [
    ...Object.entries(KEY_NAMES_BY_POSITION),
    ...Object.entries(DIRECT_SYSTEM_KEYS),
    ...Object.entries(SYSTEM_KEYS_BY_POSITION),
    ...Object.entries(FUNCTION_KEYS),
  ].map(([position, keyName]) => [keyName, position]),
);

const FUNCTION_LAYER_KEY_NAMES = new Set([
  ...Array.from({ length: 12 }, (_, index) => `KEY_F${index + 1}`),
  "KEY_DELETE",
  "KEY_LEFTMETA",
]);

const FUNCTION_LAYER_REPLACED_KEY_NAMES = new Set(
  Object.entries(KEY_NAMES_BY_POSITION)
    .filter(([position]) => position.startsWith("0:") && position !== "0:0")
    .map(([, keyName]) => keyName),
);

export const isKeyNameVisibleInLayer = (
  keyName: string,
  systemMode: boolean,
  functionLayer: boolean,
): boolean => {
  if (
    keyName === "KEY_ESC"
    || keyName === "KEY_LEFTCTRL"
    || keyName === "KEY_LEFTALT"
  ) {
    return systemMode;
  }
  if (keyName === "KEY_GRAVE")
    return !systemMode;
  if (FUNCTION_LAYER_KEY_NAMES.has(keyName))
    return systemMode && functionLayer;
  if (FUNCTION_LAYER_REPLACED_KEY_NAMES.has(keyName))
    return !systemMode || !functionLayer;
  return true;
};

export const languageSwitchModifiers = (
  shortcut: LanguageSwitchShortcut,
): { keyName: string; withAlt: boolean; withControl: boolean; withMeta: boolean } => ({
  keyName: shortcut === "meta-space" ? "KEY_SPACE" : "KEY_LEFTSHIFT",
  withAlt: shortcut === "alt-shift",
  withControl: shortcut === "ctrl-shift",
  withMeta: shortcut === "meta-space",
});

export const keyPosition = (key: HTMLElement): string =>
  `${key.dataset.keyRow}:${key.dataset.keyCol}`;

export const resolveLanguageSwitchOption = (
  key: HTMLElement,
): LanguageSwitchOption | undefined =>
  LANGUAGE_SWITCH_OPTIONS_BY_POSITION.get(keyPosition(key));

export const resolveSystemKey = (
  key: HTMLElement,
  functionLayer: boolean,
  modifierActive: boolean,
): string | undefined => {
  const position = keyPosition(key);
  return DIRECT_SYSTEM_KEYS[position]
    ?? (functionLayer
      ? FUNCTION_KEYS_BY_NAME[key.dataset.key ?? ""]
      : undefined)
    ?? (functionLayer ? FUNCTION_KEYS[position] : undefined)
    ?? (modifierActive
      ? SYSTEM_KEYS_BY_NAME[key.dataset.key ?? ""]
        ?? SYSTEM_KEYS_BY_POSITION[position]
        ?? KEY_NAMES_BY_POSITION[position]
      : undefined);
};

export const isAltKey = (key: HTMLElement): boolean =>
  key.dataset.key === NATIVE_ALT_KEY
  || key.dataset.key === SYNTHETIC_ALT_KEY;

export const isShiftKey = (key: HTMLElement): boolean =>
  keyPosition(key) === "3:0";

export const findKey = (
  keyboard: HTMLElement,
  row: number,
  column: number,
): HTMLElement | null => keyboard.querySelector(
  `${KEY_SELECTOR}[data-key-row="${row}"][data-key-col="${column}"]`,
);

export const findNamedKey = (
  keyboard: HTMLElement,
  name: string,
): HTMLElement | null =>
  keyboard.querySelector(`${KEY_SELECTOR}[data-key="${name}"]`);

export const findKeyBySystemName = (
  keyboard: HTMLElement,
  keyName: string,
): HTMLElement | null => {
  const position = POSITIONS_BY_KEY_NAME.get(keyName);
  if (!position)
    return null;
  const [row, column] = position.split(":").map(Number);
  return findKey(keyboard, row, column);
};
