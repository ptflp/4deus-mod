const MOD_CLASS_PREFIX = "fourdeus-";
const KEY_SELECTOR = "div[data-key-row][data-key-col]";
const SHIFT_KEY_ROW = "3";
const SHIFT_KEY_COLUMN = "0";
export const KEYBOARD_IDENTITY_ATTRIBUTES = [
  "data-key",
  "data-key-col",
  "data-key-row",
];
export const SHIFT_STATE_ATTRIBUTES = ["class"];
const MOD_NODE_SELECTOR = [
  ".fourdeus-secondary-label",
  ".fourdeus-hold-hint-label",
  ".fourdeus-swapped-native-label",
  ".fourdeus-swapped-primary-label",
  ".fourdeus-system-key-label",
  ".fourdeus-deck-binding-label",
  ".fourdeus-language-switch-option-label",
  '[data-key="4deus_Alt"]',
  '[data-key="4deus_Fn"]',
].join(",");

export const normalizedNativeClasses = (value: string | null): string =>
  (value ?? "")
    .split(/\s+/u)
    .filter((className) =>
      className && !className.startsWith(MOD_CLASS_PREFIX),
    )
    .join(" ");

export const isRelevantKeyClassChange = (
  oldValue: string | null,
  currentValue: string | null,
  shiftKey: boolean,
): boolean =>
  shiftKey
  && normalizedNativeClasses(oldValue) !== normalizedNativeClasses(currentValue);

const isModNode = (node: Node): boolean => {
  const element = node.nodeType === 1
    ? node as Element
    : node.parentElement;
  return Boolean(element?.closest?.(MOD_NODE_SELECTOR));
};

const containingKey = (node: Node): HTMLElement | undefined => {
  const element = node.nodeType === 1
    ? node as Element
    : node.parentElement;
  return element?.closest?.<HTMLElement>(KEY_SELECTOR) ?? undefined;
};

const isShiftKey = (key: HTMLElement): boolean =>
  key.dataset.keyRow === SHIFT_KEY_ROW
  && key.dataset.keyCol === SHIFT_KEY_COLUMN;

const hasNativeNode = (nodes: NodeList): boolean => {
  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes.item(index);
    if (node && !isModNode(node))
      return true;
  }
  return false;
};

const hasNativeChildChange = (mutation: MutationRecord): boolean =>
  hasNativeNode(mutation.addedNodes)
  || hasNativeNode(mutation.removedNodes);

export const isRelevantKeyboardMutation = (
  mutation: MutationRecord,
): boolean => {
  if (isModNode(mutation.target))
    return false;

  const key = containingKey(mutation.target);
  if (mutation.type === "characterData")
    return !key;

  if (mutation.type === "childList") {
    // Steam adds and removes focus/ripple nodes inside a key on every press.
    // Key identity changes are reported separately through data-key.
    return hasNativeChildChange(mutation) && !key;
  }

  if (mutation.attributeName !== "class")
    return true;
  const current = (mutation.target as Element).getAttribute("class");
  // Regular keys and keyboard containers change native classes for focus,
  // press, and animation. Only a native Shift state change affects labels.
  return isRelevantKeyClassChange(
    mutation.oldValue,
    current,
    Boolean(key && isShiftKey(key)),
  );
};

export const hasRelevantKeyboardMutation = (
  mutations: MutationRecord[],
): boolean => mutations.some(isRelevantKeyboardMutation);
