import { findModuleExport } from "@decky/ui";

import { AUTO_LAYOUT } from "../../core/settings";

interface KeyboardLayoutSettings {
  currentLayout: number;
  selectedLayouts: number[];
}

interface KeyboardLayoutStore {
  GetKeyboardLayoutSettings(): KeyboardLayoutSettings;
  SetKeyboardLayout(layout: number): void;
}

type LayoutKey =
  | string
  | null
  | undefined
  | LayoutKey[]
  | {
    key?: string;
    label?: unknown;
  };

export interface SteamKeyboardLayout {
  name: string;
  layout: number;
  locToken: string;
  rgLayout(options: Record<string, boolean>): LayoutKey[][];
}

let layoutStore: KeyboardLayoutStore | undefined;
let activeLayoutsProvider: (() => SteamKeyboardLayout[]) | undefined;

const resolveSteamModules = (): void => {
  layoutStore ??= findModuleExport(
    (value) =>
      value
      && typeof value.GetKeyboardLayoutSettings === "function"
      && typeof value.SetKeyboardLayout === "function",
  ) as KeyboardLayoutStore | undefined;

  activeLayoutsProvider ??= findModuleExport(
    (value) => {
      if (typeof value !== "function")
        return false;
      const source = value.toString();
      return source.includes("GetKeyboardLayoutSettings")
        && source.includes("selectedLayouts")
        && source.includes(".filter");
    },
  ) as (() => SteamKeyboardLayout[]) | undefined;
};

export const getEnabledLayouts = (): SteamKeyboardLayout[] => {
  resolveSteamModules();
  try {
    return activeLayoutsProvider?.() ?? [];
  } catch (error) {
    console.warn("[4deus Mod/Keyboard] Steam layouts are unavailable", error);
    return [];
  }
};

export const getLayoutDisplayName = (layout: SteamKeyboardLayout): string => {
  const localized = window.LocalizationManager?.m_mapTokens?.get(layout.locToken);
  if (localized)
    return localized;

  return layout.name
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
};

const getPrimaryLabel = (key: LayoutKey): string | undefined => {
  if (typeof key === "string")
    return key;
  if (Array.isArray(key))
    return getPrimaryLabel(key[0]);
  if (!key)
    return undefined;
  if (typeof key.label === "string")
    return key.label;
  return key.key;
};

const selectSecondaryLayout = (
  layouts: SteamKeyboardLayout[],
  preferredLayout: string,
): SteamKeyboardLayout | undefined => {
  const settings = layoutStore?.GetKeyboardLayoutSettings();
  const currentLayout = settings?.currentLayout;
  const preferred = preferredLayout === AUTO_LAYOUT
    ? undefined
    : layouts.find((layout) => layout.layout === Number(preferredLayout));
  const selected = (settings?.selectedLayouts ?? [])
    .map((layoutID) =>
      layouts.find((layout) => layout.layout === layoutID),
    );
  return [preferred, ...selected, ...layouts].find(
    (layout): layout is SteamKeyboardLayout =>
      Boolean(layout && layout.layout !== currentLayout),
  );
};

export const buildSecondaryLabelMap = (
  preferredLayout: string,
): Map<string, string> => {
  resolveSteamModules();
  const layout = selectSecondaryLayout(getEnabledLayouts(), preferredLayout);
  if (!layout)
    return new Map();

  const labels = new Map<string, string>();
  const rows = layout.rgLayout({
    AllowMove: false,
    Arrows: false,
    DoneInsteadOfHide: false,
    Paste: false,
  });

  rows.forEach((row, rowIndex) => {
    row.forEach((key, columnIndex) => {
      const label = getPrimaryLabel(key);
      if (label && /^\p{L}$/u.test(label))
        labels.set(`${rowIndex}:${columnIndex}`, label);
    });
  });

  return labels;
};
