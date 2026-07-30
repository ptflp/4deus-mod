import { findModuleExport } from "@decky/ui";

import {
  getVariantLabel,
  isSecondaryLabelRow,
  isSingleCharacter,
  type LayoutKey,
} from "./layoutLabels";
import {
  activateQwertyLayout,
  type KeyboardLayoutController,
  selectSecondaryLayout,
  shouldShowSecondaryLayer,
} from "./layoutSelection";

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

let layoutStore: KeyboardLayoutController | undefined;
let activeLayoutsProvider: (() => SteamKeyboardLayout[]) | undefined;
let secondaryLabelCache:
  | { key: string; labels: SecondaryLabelMap }
  | undefined;

const resolveSteamModules = (): void => {
  layoutStore ??= findModuleExport(
    (value) =>
      value
      && typeof value.GetKeyboardLayoutSettings === "function",
  ) as KeyboardLayoutController | undefined;

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

export const activateQwertyKeyboardLayout = (): boolean => {
  resolveSteamModules();
  try {
    return activateQwertyLayout(layoutStore);
  } catch (error) {
    console.warn(
      "[4deus Mod/Keyboard] Failed to activate Steam's QWERTY layout",
      error,
    );
    return false;
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

export const buildSecondaryLabelMap = (
  preferredLayout: string,
  qwertyOnly = true,
): SecondaryLabelMap => {
  resolveSteamModules();
  const settings = layoutStore?.GetKeyboardLayoutSettings();
  if (!shouldShowSecondaryLayer(settings?.currentLayout, qwertyOnly))
    return new Map();
  const layout = selectSecondaryLayout(
    getEnabledLayouts(),
    preferredLayout,
    settings,
  );
  if (!layout)
    return new Map();
  const cacheKey = [
    preferredLayout,
    qwertyOnly,
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
    if (!isSecondaryLabelRow(rowIndex))
      return;
    row.forEach((key, columnIndex) => {
      const normal = getVariantLabel(key, 0);
      const shifted = getVariantLabel(key, 1);
      const hasNormal = isSingleCharacter(normal);
      const hasShifted = isSingleCharacter(shifted);
      if (hasNormal || hasShifted) {
        labels.set(`${rowIndex}:${columnIndex}`, {
          normal: hasNormal ? normal : undefined,
          shifted: hasShifted ? shifted : undefined,
        });
      }
    });
  });

  secondaryLabelCache = { key: cacheKey, labels };
  return labels;
};
