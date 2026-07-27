export const EMOJI_KEY = "SwitchKeys_Steam";
export const LAYOUT_KEY = "SwitchKeys_Layout";
export const NATIVE_ALT_KEY = "AltGr";
export const SYNTHETIC_ALT_KEY = "4deus_Alt";
export const KEY_SELECTOR = "[data-key-row][data-key-col]";

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

export const keyPosition = (key: HTMLElement): string =>
  `${key.dataset.keyRow}:${key.dataset.keyCol}`;

export const resolveSystemKey = (
  key: HTMLElement,
  functionLayer: boolean,
  modifierActive: boolean,
): string | undefined => {
  const position = keyPosition(key);
  return DIRECT_SYSTEM_KEYS[position]
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
