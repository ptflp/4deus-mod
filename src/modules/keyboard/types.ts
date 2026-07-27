export interface VirtualKeyboardManager {
  IsShowingVirtualKeyboard?: {
    Value: boolean;
  };
  m_bDismissOnEnter?: boolean;
  SetDismissOnEnterKey?: (dismiss: boolean) => void;
  SetVirtualKeyboardHidden?: () => void;
}

export interface WindowInstance {
  BrowserWindow: Window;
  LocationPathName?: string;
  NavigateWithoutChangingFocus?: (
    path: string,
    replace?: boolean,
    force?: boolean,
  ) => void;
  VirtualKeyboardManager?: VirtualKeyboardManager;
}

export interface NativeSteamWindow {
  BringToFront?: (mode?: number) => void;
  MarkLastFocused?: () => void;
  SetKeyFocus?: (focused: boolean) => void;
  ShowWindow?: () => void;
}

export interface KeyboardChordEvent {
  bChordInvoked?: boolean;
}

export interface SteamInputKeyboardEvents {
  RegisterForUserKeyboardMessages?: (
    callback: (event: KeyboardChordEvent) => void,
  ) => {
    unregister(): void;
  };
}
