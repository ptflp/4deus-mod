import { DECK_QUICK_KEY_GROUPS } from "../keyboard/deckButtonBindings";

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

export const NESTED_DESKTOP_ACTION_OPTIONS = [
  { data: "none", label: "—" },
  {
    label: "Steam / Mouse",
    options: [
      { data: "SHOW_KEYBOARD", label: "⌨ Keyboard" },
      { data: "MOUSE_LEFT", label: "Mouse 1" },
      { data: "MOUSE_RIGHT", label: "Mouse 2" },
      { data: "MOUSE_MIDDLE", label: "Mouse 3" },
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
  ...DECK_QUICK_KEY_GROUPS.map((group) => ({
    label: group.label,
    options: group.options.map((option) => ({
      data: option.keyName,
      label: option.label,
    })),
  })),
];
