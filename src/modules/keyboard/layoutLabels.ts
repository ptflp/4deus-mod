export type LayoutKey =
  | string
  | null
  | undefined
  | LayoutKey[]
  | {
    key?: string;
    label?: unknown;
  };

const primaryLabel = (key: LayoutKey): string | undefined => {
  if (typeof key === "string")
    return key;
  if (Array.isArray(key))
    return primaryLabel(key[0]);
  if (!key)
    return undefined;
  if (typeof key.label === "string")
    return key.label;
  return key.key;
};

export const getVariantLabel = (
  key: LayoutKey,
  variant: number,
): string | undefined => {
  if (!Array.isArray(key))
    return variant === 0 ? primaryLabel(key) : undefined;
  return primaryLabel(key[variant]);
};

export const isSingleCharacter = (
  label: string | undefined,
): label is string => {
  if (!label || /\s/u.test(label))
    return false;
  const characters = label[Symbol.iterator]();
  return !characters.next().done && characters.next().done === true;
};

export const isSecondaryLabelRow = (row: number): boolean =>
  row >= 0 && row <= 3;

export const isVisualSwapRow = (row: number): boolean =>
  row >= 1 && row <= 3;

export const selectSecondaryLabel = (
  normal: string | undefined,
  shifted: string | undefined,
  row: number,
  keyboardShifted: boolean,
): string | undefined =>
  row === 0 || keyboardShifted
    ? shifted ?? normal
    : normal;
