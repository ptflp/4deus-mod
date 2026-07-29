import type { VirtualKeyboardManager } from "./types";

export const isVirtualKeyboardVisible = (
  manager: VirtualKeyboardManager | undefined,
  keyboardPresent: boolean,
): boolean => {
  const visible = manager?.IsShowingVirtualKeyboard?.Value;
  return typeof visible === "boolean" ? visible : keyboardPresent;
};
