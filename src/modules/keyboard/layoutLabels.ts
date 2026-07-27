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
): label is string =>
  Boolean(label && !/\s/u.test(label) && Array.from(label).length === 1);
