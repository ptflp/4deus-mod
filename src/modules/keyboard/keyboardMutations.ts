const MOD_CLASS_PREFIX = "fourdeus-";
const MOD_NODE_SELECTOR = [
  ".fourdeus-secondary-label",
  ".fourdeus-system-key-label",
  ".fourdeus-deck-binding-label",
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

const isModNode = (node: Node): boolean => {
  const element = node.nodeType === 1
    ? node as Element
    : node.parentElement;
  return Boolean(element?.closest?.(MOD_NODE_SELECTOR));
};

export const isRelevantKeyboardMutation = (
  mutation: MutationRecord,
): boolean => {
  if (mutation.type === "characterData")
    return !isModNode(mutation.target);

  if (mutation.type === "childList") {
    const changedNodes = [
      ...Array.from(mutation.addedNodes),
      ...Array.from(mutation.removedNodes),
    ];
    return changedNodes.some((node) => !isModNode(node));
  }

  if (isModNode(mutation.target))
    return false;
  if (mutation.attributeName !== "class")
    return true;

  const current = (mutation.target as Element).getAttribute("class");
  return normalizedNativeClasses(mutation.oldValue)
    !== normalizedNativeClasses(current);
};

export const hasRelevantKeyboardMutation = (
  mutations: MutationRecord[],
): boolean => mutations.some(isRelevantKeyboardMutation);
