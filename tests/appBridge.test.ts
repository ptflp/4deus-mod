import assert from "node:assert/strict";
import test from "node:test";

import {
  ensureAppBridgeShortcut,
  ensureSteamOsShortcut,
  findShortcutByName,
  findSteamOsShortcut,
} from "../src/modules/appBridge/steamShortcuts.ts";

const NON_STEAM_APP_TYPE = 1 << 30;

const installWindowMock = (includeExisting = true) => {
  const calls: Array<[string, ...unknown[]]> = [];
  const apps = includeExisting ? [
    {
      appid: 42,
      app_type: NON_STEAM_APP_TYPE,
      display_name: "Parsec",
    },
  ] : [];
  const methods = {
    AddShortcut: async (...args: unknown[]): Promise<number> => {
      calls.push(["add", ...args]);
      apps.push({
        appid: 99,
        app_type: NON_STEAM_APP_TYPE,
        display_name: args[0] as string,
      });
      return 99;
    },
    SetShortcutExe: (...args: unknown[]) => calls.push(["exe", ...args]),
    SetShortcutIcon: (...args: unknown[]) => calls.push(["icon", ...args]),
    SetShortcutLaunchOptions: (...args: unknown[]) =>
      calls.push(["options", ...args]),
    SetShortcutName: (...args: unknown[]) => calls.push(["name", ...args]),
    SetShortcutStartDir: (...args: unknown[]) =>
      calls.push(["directory", ...args]),
  };
  (globalThis as unknown as { window: unknown }).window = {
    SteamClient: { Apps: methods },
    appStore: {
      GetAppOverviewByAppID: (appId: number) =>
        apps.find((app) => app.appid === appId),
      allApps: apps,
    },
    setTimeout: (callback: () => void) => globalThis.setTimeout(callback, 0),
  };
  return { calls };
};

test("App Bridge reuses an existing non-Steam shortcut by name", async () => {
  const { calls } = installWindowMock();
  assert.equal(findShortcutByName("Parsec")?.appid, 42);

  const appId = await ensureAppBridgeShortcut({
    icon: "/icons/parsec.png",
    id: "parsec",
    launcherPath: "/home/deck/.local/bin/4deus-app-bridge",
    name: "Parsec",
    startDirectory: "/home/deck/.local/bin",
  });

  assert.equal(appId, 42);
  assert.deepEqual(calls, [
    ["name", 42, "Parsec"],
    ["exe", 42, "/home/deck/.local/bin/4deus-app-bridge"],
    ["directory", 42, "/home/deck/.local/bin"],
    ["options", 42, "parsec"],
    ["icon", 42, "/icons/parsec.png"],
  ]);
});

test("App Bridge honors a remembered shortcut ID", () => {
  installWindowMock();
  assert.equal(findShortcutByName("Parsec", 42)?.appid, 42);
  assert.equal(findShortcutByName("Missing", 42), undefined);
});

test("App Bridge reapplies every field after creating a shortcut", async () => {
  const { calls } = installWindowMock(false);
  const profile = {
    icon: "/icons/parsec.png",
    id: "parsec",
    launcherPath: "/home/deck/.local/bin/4deus-app-bridge",
    name: "Parsec",
    startDirectory: "/flatpak/parsec/files/bin",
  };

  assert.equal(await ensureAppBridgeShortcut(profile), 99);
  const configuration = [
    ["name", 99, "Parsec"],
    ["exe", 99, "/home/deck/.local/bin/4deus-app-bridge"],
    ["directory", 99, "/flatpak/parsec/files/bin"],
    ["options", 99, "parsec"],
    ["icon", 99, "/icons/parsec.png"],
  ];
  assert.deepEqual(calls, [
    [
      "add",
      "Parsec",
      "/home/deck/.local/bin/4deus-app-bridge",
      "/flatpak/parsec/files/bin",
      "parsec",
    ],
    ...configuration,
    ...configuration,
  ]);
});

test("SteamOS setup repairs a Nested Desktop shortcut in place", async () => {
  const { calls } = installWindowMock(false);
  window.appStore.allApps.push({
    appid: 77,
    app_type: NON_STEAM_APP_TYPE,
    display_name: "Nested Desktop",
  });
  assert.equal(findSteamOsShortcut()?.appid, 77);

  const appId = await ensureSteamOsShortcut({
    aliases: ["Steam Os", "Nested Desktop"],
    available: true,
    current: true,
    icon: "/usr/share/steamos/icon.png",
    launchOptions: "",
    launcherPath: "/home/deck/.local/bin/4deus-steamos-desktop",
    name: "Steam Os",
    startDirectory: "/home/deck/.local/bin",
    wrapperInstalled: true,
    wrapperPath: "/home/deck/.local/bin/4deus-steamos-desktop",
  });

  assert.equal(appId, 77);
  assert.deepEqual(calls, [
    ["name", 77, "Steam Os"],
    ["exe", 77, "/home/deck/.local/bin/4deus-steamos-desktop"],
    ["directory", 77, "/home/deck/.local/bin"],
    ["options", 77, ""],
    ["icon", 77, "/usr/share/steamos/icon.png"],
  ]);
});

test("SteamOS setup creates a shortcut without launch options", async () => {
  const { calls } = installWindowMock(false);
  const profile = {
    aliases: ["Steam Os", "Nested Desktop"],
    available: true,
    current: true,
    icon: "/usr/share/steamos/icon.png",
    launchOptions: "",
    launcherPath: "/home/deck/.local/bin/4deus-steamos-desktop",
    name: "Steam Os",
    startDirectory: "/home/deck/.local/bin",
    wrapperInstalled: true,
    wrapperPath: "/home/deck/.local/bin/4deus-steamos-desktop",
  };

  assert.equal(await ensureSteamOsShortcut(profile), 99);
  assert.deepEqual(calls[0], [
    "add",
    "Steam Os",
    "/home/deck/.local/bin/4deus-steamos-desktop",
    "/home/deck/.local/bin",
    "",
  ]);
});
