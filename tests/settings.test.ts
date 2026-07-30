import assert from "node:assert/strict";
import test from "node:test";

import { SettingsStore } from "../src/core/settings.ts";

const STORAGE_KEY = "4deus-mod.settings";

class MemoryStorage {
  private readonly values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

test("keyboard diagnostics reset after the settings store reloads", () => {
  const previousStorage = globalThis.localStorage;
  const storage = new MemoryStorage();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storage,
  });

  try {
    storage.setItem(
      STORAGE_KEY,
      JSON.stringify({ keyboard: { diagnostics: true } }),
    );

    const loaded = new SettingsStore();
    assert.equal(loaded.getSnapshot().keyboard.diagnostics, false);

    loaded.updateKeyboard({ diagnostics: true });
    assert.equal(loaded.getSnapshot().keyboard.diagnostics, true);

    const reloaded = new SettingsStore();
    assert.equal(reloaded.getSnapshot().keyboard.diagnostics, false);
  } finally {
    if (previousStorage === undefined)
      Reflect.deleteProperty(globalThis, "localStorage");
    else
      Object.defineProperty(globalThis, "localStorage", {
        configurable: true,
        value: previousStorage,
      });
  }
});
