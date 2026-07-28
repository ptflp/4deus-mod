import type { PreparedAppBridgeProfile } from "./types";

const NON_STEAM_APP_TYPE = 1 << 30;
const REGISTRATION_TIMEOUT_MS = 3000;

export interface ShortcutOverview {
  appid: number;
  app_type: number;
  display_name: string;
}

const shortcutById = (appId: number | undefined): ShortcutOverview | undefined => {
  if (!appId)
    return undefined;
  const overview = window.appStore.GetAppOverviewByAppID(appId);
  return overview?.app_type === NON_STEAM_APP_TYPE ? overview : undefined;
};

export const findShortcutByName = (
  name: string,
  preferredAppId?: number,
): ShortcutOverview | undefined => {
  const preferred = shortcutById(preferredAppId);
  if (preferred?.display_name.localeCompare(name, undefined, {
    sensitivity: "accent",
  }) === 0) {
    return preferred;
  }
  return window.appStore.allApps.find((app) =>
    app.app_type === NON_STEAM_APP_TYPE
    && app.display_name.localeCompare(name, undefined, {
      sensitivity: "accent",
    }) === 0
  );
};

const waitForShortcut = async (appId: number): Promise<void> => {
  const deadline = Date.now() + REGISTRATION_TIMEOUT_MS;
  while (!window.appStore.GetAppOverviewByAppID(appId)) {
    if (Date.now() >= deadline)
      return;
    await new Promise((resolve) => window.setTimeout(resolve, 100));
  }
};

const applyShortcutConfiguration = (
  appId: number,
  profile: PreparedAppBridgeProfile,
): void => {
  window.SteamClient.Apps.SetShortcutName(appId, profile.name);
  window.SteamClient.Apps.SetShortcutExe(appId, profile.launcherPath);
  window.SteamClient.Apps.SetShortcutStartDir(
    appId,
    profile.startDirectory,
  );
  window.SteamClient.Apps.SetShortcutLaunchOptions(appId, profile.id);
  if (profile.icon.startsWith("/"))
    window.SteamClient.Apps.SetShortcutIcon(appId, profile.icon);
};

export const ensureAppBridgeShortcut = async (
  profile: PreparedAppBridgeProfile,
  preferredAppId?: number,
): Promise<number> => {
  if (profile.error)
    throw new Error(profile.error);
  const existing = findShortcutByName(profile.name, preferredAppId);
  const appId = existing?.appid ?? await window.SteamClient.Apps.AddShortcut(
    profile.name,
    profile.launcherPath,
    profile.startDirectory,
    profile.id,
  );
  if (!appId)
    throw new Error("Steam did not create the shortcut");
  if (!existing)
    await waitForShortcut(appId);

  applyShortcutConfiguration(appId, profile);
  if (!existing) {
    await new Promise((resolve) => window.setTimeout(resolve, 500));
    applyShortcutConfiguration(appId, profile);
  }
  return appId;
};
