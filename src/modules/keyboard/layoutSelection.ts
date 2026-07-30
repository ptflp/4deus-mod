const AUTO_LAYOUT = "auto";
export const QWERTY_LAYOUT = 0;

export interface SelectableKeyboardLayout {
  layout: number;
}

export interface KeyboardLayoutSelection {
  currentLayout: number;
  selectedLayouts: number[];
}

export interface KeyboardLayoutController {
  GetKeyboardLayoutSettings(): KeyboardLayoutSelection;
  SetKeyboardLayout?(layout: number): void;
}

export const activateQwertyLayout = (
  controller: KeyboardLayoutController | undefined,
): boolean => {
  if (!controller)
    return false;
  if (
    controller.GetKeyboardLayoutSettings().currentLayout
    === QWERTY_LAYOUT
  ) {
    return true;
  }
  if (!controller.SetKeyboardLayout)
    return false;
  controller.SetKeyboardLayout(QWERTY_LAYOUT);
  return true;
};

export const shouldShowSecondaryLayer = (
  currentLayout: number | undefined,
  qwertyOnly: boolean,
): boolean =>
  !qwertyOnly
  || currentLayout === undefined
  || currentLayout === QWERTY_LAYOUT;

export const selectSecondaryLayout = <
  Layout extends SelectableKeyboardLayout,
>(
  layouts: readonly Layout[],
  preferredLayout: string,
  settings: KeyboardLayoutSelection | undefined,
): Layout | undefined => {
  const currentLayout = settings?.currentLayout;
  const preferred = preferredLayout === AUTO_LAYOUT
    ? undefined
    : layouts.find((layout) => layout.layout === Number(preferredLayout));
  const selected = (settings?.selectedLayouts ?? [])
    .map((layoutID) =>
      layouts.find((layout) => layout.layout === layoutID),
    );
  return [preferred, ...selected, ...layouts].find(
    (layout): layout is Layout =>
      Boolean(layout && layout.layout !== currentLayout),
  );
};
