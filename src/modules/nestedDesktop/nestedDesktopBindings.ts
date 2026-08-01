import type { Strings } from "../../core/translations";
import { getDeckQuickKeyGroups } from "../keyboard/deckButtonBindings";

export type NestedDesktopBindingSource =
  | "a"
  | "b"
  | "x"
  | "y"
  | "dpadUp"
  | "dpadRight"
  | "dpadLeft"
  | "dpadDown"
  | "leftStickUp"
  | "leftStickRight"
  | "leftStickLeft"
  | "leftStickDown"
  | "view"
  | "menu"
  | "l1"
  | "r1"
  | "l2"
  | "r2"
  | "l3"
  | "r3"
  | "l4"
  | "r4"
  | "l5"
  | "r5"
  | "leftPadClick"
  | "rightPadClick";

export type NestedDesktopBindingAction = string;
export type NestedDesktopBindings = Record<
  NestedDesktopBindingSource,
  NestedDesktopBindingAction
>;

interface BindingSourceOption {
  label: string;
  source: NestedDesktopBindingSource;
}

export const NESTED_DESKTOP_BINDING_GROUPS: ReadonlyArray<{
  sources: readonly BindingSourceOption[];
  title: string;
}> = [
  {
    title: "A / B / X / Y",
    sources: [
      { source: "a", label: "A" },
      { source: "b", label: "B" },
      { source: "x", label: "X" },
      { source: "y", label: "Y" },
    ],
  },
  {
    title: "D-pad / Left Stick",
    sources: [
      { source: "dpadUp", label: "D-pad ↑" },
      { source: "dpadRight", label: "D-pad →" },
      { source: "dpadLeft", label: "D-pad ←" },
      { source: "dpadDown", label: "D-pad ↓" },
      { source: "leftStickUp", label: "Left Stick ↑" },
      { source: "leftStickRight", label: "Left Stick →" },
      { source: "leftStickLeft", label: "Left Stick ←" },
      { source: "leftStickDown", label: "Left Stick ↓" },
    ],
  },
  {
    title: "Menu / L / R",
    sources: [
      { source: "view", label: "View" },
      { source: "menu", label: "Menu" },
      { source: "l1", label: "L1" },
      { source: "r1", label: "R1" },
      { source: "l2", label: "L2" },
      { source: "r2", label: "R2" },
      { source: "l3", label: "L3" },
      { source: "r3", label: "R3" },
      { source: "l4", label: "L4" },
      { source: "r4", label: "R4" },
      { source: "l5", label: "L5" },
      { source: "r5", label: "R5" },
    ],
  },
  {
    title: "Trackpads",
    sources: [
      { source: "leftPadClick", label: "Left Trackpad Click" },
      { source: "rightPadClick", label: "Right Trackpad Click" },
    ],
  },
];

const localizedBindingLabel = (
  source: NestedDesktopBindingSource,
  strings: Strings,
): string | undefined => {
  if (source.startsWith("dpad"))
    return strings.nestedDesktopBindingDpad;
  if (source.startsWith("leftStick"))
    return strings.nestedDesktopBindingLeftStick;
  const labels: Partial<Record<NestedDesktopBindingSource, string>> = {
    leftPadClick: strings.nestedDesktopBindingLeftTrackpadClick,
    menu: strings.nestedDesktopBindingMenu,
    rightPadClick: strings.nestedDesktopBindingRightTrackpadClick,
    view: strings.nestedDesktopBindingView,
  };
  return labels[source];
};

const bindingDirection = (label: string): string =>
  ["↑", "→", "←", "↓"].find((direction) => label.endsWith(direction)) ?? "";

export const getNestedDesktopBindingGroups = (
  strings: Strings,
): typeof NESTED_DESKTOP_BINDING_GROUPS =>
  NESTED_DESKTOP_BINDING_GROUPS.map((group, groupIndex) => ({
    title: [
      group.title,
      strings.nestedDesktopBindingGroupDpadStick,
      strings.nestedDesktopBindingGroupMenuButtons,
      strings.nestedDesktopBindingGroupTrackpads,
    ][groupIndex],
    sources: group.sources.map(({ source, label }) => {
      const localized = localizedBindingLabel(source, strings);
      return {
        source,
        label: localized
          ? `${localized}${bindingDirection(label) ? ` ${bindingDirection(label)}` : ""}`
          : label,
      };
    }),
  }));

export const getNestedDesktopActionOptions = (strings: Strings) => [
  { data: "none", label: "—" },
  {
    label: "Steam / 🖱",
    options: [
      {
        data: "SHOW_KEYBOARD",
        label: `⌨ ${strings.nestedDesktopBindingKeyboard}`,
      },
      { data: "MOUSE_LEFT", label: strings.nestedDesktopBindingMousePrimary },
      {
        data: "MOUSE_RIGHT",
        label: strings.nestedDesktopBindingMouseSecondary,
      },
      {
        data: "MOUSE_MIDDLE",
        label: strings.nestedDesktopBindingMouseMiddle,
      },
    ],
  },
  {
    label: "Ctrl / Alt / Shift / Meta",
    options: [
      { data: "KEY_LEFTCTRL", label: "Ctrl" },
      { data: "KEY_LEFTALT", label: "Alt" },
      { data: "KEY_LEFTSHIFT", label: "Shift" },
      { data: "KEY_LEFTMETA", label: "Meta" },
    ],
  },
  ...getDeckQuickKeyGroups(strings).map((group) => ({
    label: group.label,
    options: group.options.map((option) => ({
      data: option.keyName,
      label: option.label,
    })),
  })),
];
