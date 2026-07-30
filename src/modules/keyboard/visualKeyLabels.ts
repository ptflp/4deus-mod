export interface VisualKeyLabels {
  primary?: string;
  secondary?: string;
}

export const resolveVisualKeyLabels = (
  nativePrimary: string | undefined,
  secondary: string | undefined,
  swapped: boolean,
): VisualKeyLabels => {
  if (
    !secondary
    || secondary.toLocaleLowerCase() === nativePrimary?.toLocaleLowerCase()
  ) {
    return { primary: nativePrimary };
  }
  return swapped
    ? { primary: secondary, secondary: nativePrimary }
    : { primary: nativePrimary, secondary };
};
