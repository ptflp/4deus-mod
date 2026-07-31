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
    assert.equal(loaded.getSnapshot().appBridge.enabled, true);
    assert.equal(
      loaded.getSnapshot().advancedModules.nestedDesktop,
      false,
    );
    assert.equal(loaded.getSnapshot().keyboard.autoSwapVisualLayer, true);
    assert.equal(loaded.getSnapshot().keyboard.holdHints, true);
    assert.equal(
      loaded.getSnapshot().keyboard.secondaryLabelsQwertyOnly,
      true,
    );

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

test("advanced visibility is saved independently for every module", () => {
  const previousStorage = globalThis.localStorage;
  const storage = new MemoryStorage();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storage,
  });

  try {
    const settings = new SettingsStore();
    settings.updateAdvancedModule("nestedDesktop", true);

    const reloaded = new SettingsStore();
    assert.equal(
      reloaded.getSnapshot().advancedModules.nestedDesktop,
      true,
    );
    assert.equal(
      reloaded.getSnapshot().advancedModules.keyboard,
      false,
    );
    assert.equal(
      reloaded.getSnapshot().advancedModules.controller,
      false,
    );
    assert.equal(
      reloaded.getSnapshot().advancedModules.appBridge,
      false,
    );
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

test("App Bridge module visibility persists without losing shortcuts", () => {
  const previousStorage = globalThis.localStorage;
  const storage = new MemoryStorage();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storage,
  });

  try {
    const settings = new SettingsStore();
    settings.updateAppBridge({
      enabled: false,
      shortcutAppIds: { parsec: 123 },
    });

    const reloaded = new SettingsStore();
    assert.equal(reloaded.getSnapshot().appBridge.enabled, false);
    assert.deepEqual(
      reloaded.getSnapshot().appBridge.shortcutAppIds,
      { parsec: 123 },
    );
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

test("layout swap mode and QWERTY-only second layer persist", () => {
  const previousStorage = globalThis.localStorage;
  const storage = new MemoryStorage();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storage,
  });

  try {
    storage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        keyboard: {
          languageSwitchShortcut: "swap",
          secondaryLabelsDisabledLayouts: [5, 5, "13", 2.5],
          secondaryLayerSwapped: true,
          autoSwapVisualLayer: true,
          holdHints: false,
        },
      }),
    );

    const loaded = new SettingsStore();
    assert.equal(
      loaded.getSnapshot().keyboard.languageSwitchShortcut,
      "native",
    );
    assert.equal(
      loaded.getSnapshot().keyboard.secondaryLabelsQwertyOnly,
      true,
    );
    assert.equal(
      loaded.getSnapshot().keyboard.secondaryLayerSwapped,
      true,
    );
    assert.equal(
      loaded.getSnapshot().keyboard.autoSwapVisualLayer,
      true,
    );
    assert.equal(loaded.getSnapshot().keyboard.holdHints, false);

    loaded.updateKeyboard({
      secondaryLabelsQwertyOnly: false,
      secondaryLayerSwapped: false,
      autoSwapVisualLayer: false,
    });
    const reloaded = new SettingsStore();
    assert.equal(
      reloaded.getSnapshot().keyboard.secondaryLabelsQwertyOnly,
      false,
    );
    assert.equal(
      reloaded.getSnapshot().keyboard.secondaryLayerSwapped,
      false,
    );
    assert.equal(
      reloaded.getSnapshot().keyboard.autoSwapVisualLayer,
      false,
    );
    assert.equal(reloaded.getSnapshot().keyboard.holdHints, false);
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

test("unchanged settings preserve snapshots without notifying", () => {
  const previousStorage = globalThis.localStorage;
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: new MemoryStorage(),
  });

  try {
    const settings = new SettingsStore();
    const keyboard = settings.getKeyboardSnapshot();
    const advancedModules = settings.getAdvancedModulesSnapshot();
    let updates = 0;
    settings.subscribe(() => {
      updates += 1;
    });

    settings.updateKeyboard({ keepOnTop: true });
    settings.updateAdvancedModule("keyboard", false);
    settings.updateAppBridge({ enabled: true });

    assert.equal(updates, 0);
    assert.equal(settings.getKeyboardSnapshot(), keyboard);
    assert.equal(settings.getAdvancedModulesSnapshot(), advancedModules);

    settings.updateKeyboard({ keepOnTop: false });
    assert.equal(updates, 1);
    assert.notEqual(settings.getKeyboardSnapshot(), keyboard);
    assert.equal(settings.getAdvancedModulesSnapshot(), advancedModules);
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
