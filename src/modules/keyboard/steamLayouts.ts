import { findModuleExport } from "@decky/ui";

import { AUTO_LAYOUT } from "../../core/settings";
import {
  getVariantLabel,
  isSingleCharacter,
  type LayoutKey,
} from "./layoutLabels";

interface KeyboardLayoutSettings {
  currentLayout: number;
  selectedLayouts: number[];
}

interface KeyboardLayoutStore {
  GetKeyboardLayoutSettings(): KeyboardLayoutSettings;
  SetKeyboardLayout(layout: number): void;
}

const QWERTY_LAYOUT = 0;

export interface SteamKeyboardLayout {
  name: string;
  layout: number;
  locToken: string;
  rgLayout(options: Record<string, boolean>): LayoutKey[][];
}

export interface SecondaryKeyLabels {
  normal?: string;
  shifted?: string;
}

export type SecondaryLabelMap = Map<string, SecondaryKeyLabels>;

let layoutStore: KeyboardLayoutStore | undefined;
let activeLayoutsProvider: (() => SteamKeyboardLayout[]) | undefined;
let secondaryLabelCache:
  | { key: string; labels: SecondaryLabelMap }
  | undefined;

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

export const isQwertyKeyboardLayout = (): boolean => {
  resolveSteamModules();
  try {
    const currentLayout = layoutStore?.GetKeyboardLayoutSettings()
      .currentLayout;
    return currentLayout === QWERTY_LAYOUT;
  } catch (error) {
    console.warn(
      "[4deus Mod/Keyboard] Failed to read Steam's keyboard layout",
      error,
    );
    return true;
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

const selectSecondaryLayout = (
  layouts: SteamKeyboardLayout[],
  preferredLayout: string,
  settings: KeyboardLayoutSettings | undefined,
): SteamKeyboardLayout | undefined => {
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
): SecondaryLabelMap => {
  resolveSteamModules();
  const settings = layoutStore?.GetKeyboardLayoutSettings();
  const layout = selectSecondaryLayout(
    getEnabledLayouts(),
    preferredLayout,
    settings,
  );
  if (!layout)
    return new Map();
  const cacheKey = [
    preferredLayout,
    settings?.currentLayout,
    layout.layout,
  ].join(":");
  if (secondaryLabelCache?.key === cacheKey)
    return secondaryLabelCache.labels;

  const labels: SecondaryLabelMap = new Map();
  const rows = layout.rgLayout({
    AllowMove: false,
    Arrows: false,
    DoneInsteadOfHide: false,
    Paste: false,
  });

  rows.forEach((row, rowIndex) => {
    row.forEach((key, columnIndex) => {
      const normal = getVariantLabel(key, 0);
      const shifted = getVariantLabel(key, 1);
      if (isSingleCharacter(normal) || isSingleCharacter(shifted)) {
        labels.set(`${rowIndex}:${columnIndex}`, {
          normal: isSingleCharacter(normal) ? normal : undefined,
          shifted: isSingleCharacter(shifted) ? shifted : undefined,
        });
      }
    });
  });

  secondaryLabelCache = { key: cacheKey, labels };
  return labels;
};
