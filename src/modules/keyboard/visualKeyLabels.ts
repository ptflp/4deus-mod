export interface VisualKeyLabels {
  primary?: string;
  secondary?: string;
}

export const resolveVisualKeyLabels = (
  nativePrimary: string | undefined,
  secondary: string | undefined,
  swapped: boolean,
  visibleNativeLabels: readonly string[] = [],
): VisualKeyLabels => {
  const normalizedSecondary = secondary?.toLocaleLowerCase();
  if (
    !secondary
    || normalizedSecondary === nativePrimary?.toLocaleLowerCase()
    || (
      !swapped
      && visibleNativeLabels.some(
        (label) => label.toLocaleLowerCase() === normalizedSecondary,
      )
    )
  ) {
    return { primary: nativePrimary };
  }
  return swapped
    ? { primary: secondary, secondary: nativePrimary }
    : { primary: nativePrimary, secondary };
};
