export const AUTO_LAYOUT = "auto";
export type LanguageSwitchShortcut =
  | "alt-shift"
  | "ctrl-shift"
  | "meta-space"
  | "native";
export type DeckButton =
  | "view"
  | "l1"
  | "r1"
  | "l2"
  | "r2"
  | "l3"
  | "r3"
  | "l4"
  | "r4"
  | "l5"
  | "r5";
export type DeckButtonAction =
  | "none"
  | "KEY_ESC"
  | "KEY_SPACE"
  | "KEY_BACKSPACE"
  | "KEY_ENTER"
  | "KEY_TAB"
  | "KEY_LEFTCTRL"
  | "KEY_LEFTALT"
  | "KEY_LEFTSHIFT";
export type DeckButtonBindings = Record<DeckButton, DeckButtonAction>;
export type DeckQuickAction = string;
export type DeckQuickActions = Record<DeckButton, DeckQuickAction>;

const emptyQuickActions = (): DeckQuickActions => ({
  view: "",
  l1: "",
  r1: "",
  l2: "",
  r2: "",
  l3: "",
  r3: "",
  l4: "",
  r4: "",
  l5: "",
  r5: "",
});

const LEGACY_QUICK_ACTIONS: Record<string, string> = {
  "ctrl-shift-delete": "Ctrl+Shift+Delete",
  "ctrl-alt-delete": "Ctrl+Alt+Delete",
  "ctrl-shift-esc": "Ctrl+Shift+Esc",
  "ctrl-shift-w": "Ctrl+Shift+W",
  "alt-f4": "Alt+F4",
  none: "",
};

const normalizeQuickActions = (
  actions: Partial<DeckQuickActions> | undefined,
): DeckQuickActions => {
  const normalized = emptyQuickActions();
  for (const button of Object.keys(normalized) as DeckButton[]) {
    const value = actions?.[button];
    normalized[button] = typeof value === "string"
      ? LEGACY_QUICK_ACTIONS[value] ?? value
      : "";
  }
  return normalized;
};

export interface ModSettings {
  version: 1;
  appBridge: {
    shortcutAppIds: Record<string, number>;
  };
  keyboard: {
    enabled: boolean;
    keepOnTop: boolean;
    keepOpenAfterEnter: boolean;
    systemKeyLayer: boolean;
    languageSwitchShortcutEnabled: boolean;
    languageSwitchShortcut: LanguageSwitchShortcut;
    deckButtonBindingsEnabled: boolean;
    deckButtonBindings: DeckButtonBindings;
    deckButtonQuickActionsEnabled: boolean;
    deckButtonQuickActions: DeckQuickActions;
    deckButtonSecondLayerEnabled: boolean;
    deckButtonSecondLayerActions: DeckQuickActions;
    secondaryLabels: boolean;
    secondaryLayout: string;
    diagnostics: boolean;
  };
}

type Listener = () => void;

const STORAGE_KEY = "4deus-mod.settings";

const defaults: ModSettings = {
  version: 1,
  appBridge: {
    shortcutAppIds: {},
  },
  keyboard: {
    enabled: true,
    keepOnTop: true,
    keepOpenAfterEnter: false,
    systemKeyLayer: true,
    languageSwitchShortcutEnabled: true,
    languageSwitchShortcut: "native",
    deckButtonBindingsEnabled: true,
    deckButtonBindings: {
      view: "none",
      l1: "KEY_ESC",
      r1: "KEY_SPACE",
      l2: "none",
      r2: "none",
      l3: "none",
      r3: "none",
      l4: "none",
      r4: "none",
      l5: "none",
      r5: "none",
    },
    deckButtonQuickActionsEnabled: true,
    deckButtonQuickActions: emptyQuickActions(),
    deckButtonSecondLayerEnabled: false,
    deckButtonSecondLayerActions: emptyQuickActions(),
    secondaryLabels: true,
    secondaryLayout: AUTO_LAYOUT,
    diagnostics: false,
  },
};

const readSettings = (): ModSettings => {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw)
    return defaults;

  try {
    const parsed = JSON.parse(raw) as Partial<ModSettings>;
    return {
      ...defaults,
      ...parsed,
      appBridge: {
        shortcutAppIds: {
          ...defaults.appBridge.shortcutAppIds,
          ...parsed.appBridge?.shortcutAppIds,
        },
      },
      keyboard: {
        ...defaults.keyboard,
        ...parsed.keyboard,
        deckButtonBindings: {
          ...defaults.keyboard.deckButtonBindings,
          ...parsed.keyboard?.deckButtonBindings,
        },
        deckButtonQuickActions: normalizeQuickActions(
          parsed.keyboard?.deckButtonQuickActions,
        ),
        deckButtonSecondLayerActions: normalizeQuickActions(
          parsed.keyboard?.deckButtonSecondLayerActions,
        ),
        diagnostics: false,
      },
      version: 1,
    };
  } catch (error) {
    console.warn("[4deus Mod] Ignoring invalid settings", error);
    return defaults;
  }
};

export class SettingsStore {
  private settings = readSettings();
  private readonly listeners = new Set<Listener>();

  getSnapshot = (): ModSettings => this.settings;

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  updateKeyboard(patch: Partial<ModSettings["keyboard"]>): void {
    this.settings = {
      ...this.settings,
      keyboard: {
        ...this.settings.keyboard,
        ...patch,
      },
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(this.settings));
    this.listeners.forEach((listener) => listener());
  }

  updateAppBridge(patch: Partial<ModSettings["appBridge"]>): void {
    this.settings = {
      ...this.settings,
      appBridge: {
        ...this.settings.appBridge,
        ...patch,
      },
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(this.settings));
    this.listeners.forEach((listener) => listener());
  }
}
