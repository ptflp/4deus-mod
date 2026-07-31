import assert from "node:assert/strict";
import test from "node:test";

import {
  ModuleRegistry,
  type ModuleRegistryApi,
} from "../src/core/moduleRegistry.ts";
import { SettingsStore } from "../src/core/settings.ts";

class MemoryStorage {
  private readonly values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

interface MutableBackendStatus {
  available: boolean;
  moduleEnabled: boolean;
}

class RecordingModuleApi implements ModuleRegistryApi {
  readonly controller: MutableBackendStatus = {
    available: true,
    moduleEnabled: false,
  };
  readonly nestedDesktop: MutableBackendStatus = {
    available: true,
    moduleEnabled: true,
  };
  readonly changes: [string, boolean][] = [];

  async getControllerStatus() {
    return { ...this.controller };
  }

  async setControllerModuleEnabled(enabled: boolean) {
    this.changes.push(["controller", enabled]);
    this.controller.moduleEnabled = enabled;
    return { ...this.controller };
  }

  async getNestedDesktopMouseStatus() {
    return { ...this.nestedDesktop };
  }

  async setNestedDesktopModuleEnabled(enabled: boolean) {
    this.changes.push(["nestedDesktop", enabled]);
    this.nestedDesktop.moduleEnabled = enabled;
    return { ...this.nestedDesktop };
  }
}

const withStorage = async (run: () => Promise<void>): Promise<void> => {
  const previousStorage = globalThis.localStorage;
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: new MemoryStorage(),
  });
  try {
    await run();
  } finally {
    if (previousStorage === undefined)
      Reflect.deleteProperty(globalThis, "localStorage");
    else
      Object.defineProperty(globalThis, "localStorage", {
        configurable: true,
        value: previousStorage,
      });
  }
};

test("registry combines local and backend module state", async () => {
  await withStorage(async () => {
    const settings = new SettingsStore();
    const api = new RecordingModuleApi();
    const modules = new ModuleRegistry(settings, api);
    modules.start();
    await modules.refresh();

    assert.equal(modules.getSnapshot().keyboard.enabled, true);
    assert.equal(modules.getSnapshot().controller.enabled, false);
    assert.equal(modules.getSnapshot().nestedDesktop.enabled, true);

    await modules.setEnabled("keyboard", false);
    await modules.setEnabled("controller", true);

    assert.equal(settings.getSnapshot().keyboard.enabled, false);
    assert.equal(modules.getSnapshot().keyboard.enabled, false);
    assert.equal(modules.getSnapshot().controller.enabled, true);
    assert.deepEqual(api.changes, [["controller", true]]);
    modules.stop();
  });
});

test("disabling a module preserves its feature configuration", async () => {
  await withStorage(async () => {
    const settings = new SettingsStore();
    settings.updateAppBridge({ shortcutAppIds: { rustdesk: 456 } });
    const modules = new ModuleRegistry(settings, new RecordingModuleApi());
    modules.start();

    await modules.setEnabled("appBridge", false);

    assert.equal(modules.getSnapshot().appBridge.enabled, false);
    assert.deepEqual(
      settings.getSnapshot().appBridge.shortcutAppIds,
      { rustdesk: 456 },
    );
    modules.stop();
  });
});

test("backend refresh publishes one stable snapshot", async () => {
  await withStorage(async () => {
    const settings = new SettingsStore();
    const modules = new ModuleRegistry(settings, new RecordingModuleApi());
    let updates = 0;
    modules.subscribe(() => {
      updates += 1;
    });

    await modules.refresh();
    assert.equal(updates, 1);
    const snapshot = modules.getSnapshot();

    await modules.refresh();
    assert.equal(updates, 1);
    assert.equal(modules.getSnapshot(), snapshot);
  });
});
