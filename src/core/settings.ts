export const AUTO_LAYOUT = "auto";

export interface ModSettings {
  version: 1;
  keyboard: {
    enabled: boolean;
    keepOnTop: boolean;
    secondaryLabels: boolean;
    secondaryLayout: string;
  };
}

type Listener = () => void;

const STORAGE_KEY = "4deus-mod.settings";

const defaults: ModSettings = {
  version: 1,
  keyboard: {
    enabled: true,
    keepOnTop: true,
    secondaryLabels: true,
    secondaryLayout: AUTO_LAYOUT,
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
      keyboard: {
        ...defaults.keyboard,
        ...parsed.keyboard,
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
}
