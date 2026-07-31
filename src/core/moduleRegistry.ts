import type { SettingsStore } from "./settings";

export type ModuleId =
  | "keyboard"
  | "controller"
  | "nestedDesktop"
  | "appBridge";

export interface ModuleState {
  available: boolean;
  busy: boolean;
  enabled: boolean;
  error?: string;
}

export type ModuleSnapshot = Record<ModuleId, ModuleState>;

interface BackendModuleStatus {
  available: boolean;
  error?: string;
  moduleEnabled: boolean;
}

export interface ModuleRegistryApi {
  getControllerStatus(): Promise<BackendModuleStatus>;
  setControllerModuleEnabled(
    enabled: boolean,
  ): Promise<BackendModuleStatus>;
  getNestedDesktopMouseStatus(): Promise<BackendModuleStatus>;
  setNestedDesktopModuleEnabled(
    enabled: boolean,
  ): Promise<BackendModuleStatus>;
}

type Listener = () => void;

const localState = (enabled: boolean): ModuleState => ({
  available: true,
  busy: false,
  enabled,
});

const stateMatches = (left: ModuleState, right: ModuleState): boolean =>
  left.available === right.available
  && left.busy === right.busy
  && left.enabled === right.enabled
  && left.error === right.error;

export class ModuleRegistry {
  private readonly settings: SettingsStore;
  private readonly api: ModuleRegistryApi;
  private snapshot: ModuleSnapshot;
  private readonly listeners = new Set<Listener>();
  private unsubscribeSettings?: () => void;

  constructor(
    settings: SettingsStore,
    api: ModuleRegistryApi,
  ) {
    this.settings = settings;
    this.api = api;
    const stored = settings.getSnapshot();
    this.snapshot = {
      keyboard: localState(stored.keyboard.enabled),
      controller: {
        available: true,
        busy: true,
        enabled: true,
      },
      nestedDesktop: {
        available: true,
        busy: true,
        enabled: true,
      },
      appBridge: localState(stored.appBridge.enabled),
    };
  }

  getSnapshot = (): ModuleSnapshot => this.snapshot;

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  start(): void {
    if (this.unsubscribeSettings)
      return;
    this.unsubscribeSettings = this.settings.subscribe(
      this.syncLocalModules,
    );
    this.syncLocalModules();
    void this.refresh();
  }

  stop(): void {
    this.unsubscribeSettings?.();
    this.unsubscribeSettings = undefined;
  }

  async refresh(): Promise<void> {
    const [controller, nestedDesktop] = await Promise.allSettled([
      this.api.getControllerStatus(),
      this.api.getNestedDesktopMouseStatus(),
    ]);
    const controllerState = this.settledState("controller", controller);
    const nestedDesktopState = this.settledState(
      "nestedDesktop",
      nestedDesktop,
    );
    if (
      stateMatches(this.snapshot.controller, controllerState)
      && stateMatches(this.snapshot.nestedDesktop, nestedDesktopState)
    )
      return;
    this.snapshot = {
      ...this.snapshot,
      controller: controllerState,
      nestedDesktop: nestedDesktopState,
    };
    this.emit();
  }

  async setEnabled(id: ModuleId, enabled: boolean): Promise<void> {
    if (id === "keyboard") {
      this.settings.updateKeyboard({ enabled });
      return;
    }
    if (id === "appBridge") {
      this.settings.updateAppBridge({ enabled });
      return;
    }

    this.patch(id, { busy: true, error: undefined });
    try {
      const status = id === "controller"
        ? await this.api.setControllerModuleEnabled(enabled)
        : await this.api.setNestedDesktopModuleEnabled(enabled);
      this.applyBackendStatus(id, status);
    } catch (error) {
      this.patch(id, {
        busy: false,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  private readonly syncLocalModules = (): void => {
    const stored = this.settings.getSnapshot();
    const keyboardEnabled = stored.keyboard.enabled;
    const appBridgeEnabled = stored.appBridge.enabled;
    if (
      this.snapshot.keyboard.enabled === keyboardEnabled
      && this.snapshot.appBridge.enabled === appBridgeEnabled
    )
      return;
    this.snapshot = {
      ...this.snapshot,
      keyboard: localState(keyboardEnabled),
      appBridge: localState(appBridgeEnabled),
    };
    this.emit();
  };

  private settledState(
    id: "controller" | "nestedDesktop",
    result: PromiseSettledResult<BackendModuleStatus>,
  ): ModuleState {
    if (result.status === "fulfilled")
      return this.backendState(result.value);
    return {
      ...this.snapshot[id],
      busy: false,
      error: result.reason instanceof Error
        ? result.reason.message
        : String(result.reason),
    };
  }

  private backendState(status: BackendModuleStatus): ModuleState {
    return {
      available: status.available,
      busy: false,
      enabled: status.moduleEnabled,
      error: status.error,
    };
  }

  private applyBackendStatus(
    id: "controller" | "nestedDesktop",
    status: BackendModuleStatus,
  ): void {
    this.patch(id, this.backendState(status));
  }

  private patch(id: ModuleId, patch: Partial<ModuleState>): void {
    const next = {
      ...this.snapshot[id],
      ...patch,
    };
    if (stateMatches(this.snapshot[id], next))
      return;
    this.snapshot = {
      ...this.snapshot,
      [id]: next,
    };
    this.emit();
  }

  private emit(): void {
    this.listeners.forEach((listener) => listener());
  }
}
