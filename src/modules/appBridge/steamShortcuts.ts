import type { PreparedAppBridgeProfile } from "./types";
import type {
  PreparedSteamOsApplication,
} from "../nestedDesktop/types";

const NON_STEAM_APP_TYPE = 1 << 30;
const REGISTRATION_TIMEOUT_MS = 3000;
const STEAMOS_SHORTCUT_NAMES = [
  "Steam Os",
  "Steam OS",
  "SteamOS",
  "Nested Desktop",
];

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
): ShortcutOverview | undefined => findShortcutByNames(
  [name],
  preferredAppId,
);

const shortcutNameMatches = (
  shortcut: ShortcutOverview,
  names: string[],
): boolean => names.some((name) => shortcut.display_name.localeCompare(
  name,
  undefined,
  { sensitivity: "accent" },
) === 0);

export const findShortcutByNames = (
  names: string[],
  preferredAppId?: number,
): ShortcutOverview | undefined => {
  const preferred = shortcutById(preferredAppId);
  if (preferred && shortcutNameMatches(preferred, names))
    return preferred;
  return window.appStore.allApps.find((app) => (
    app.app_type === NON_STEAM_APP_TYPE
    && shortcutNameMatches(app, names)
  )
  );
};

export const findSteamOsShortcut = (
  names: string[] = STEAMOS_SHORTCUT_NAMES,
): ShortcutOverview | undefined => {
  for (const name of names) {
    const shortcut = findShortcutByName(name);
    if (shortcut)
      return shortcut;
  }
  return undefined;
};

const waitForShortcut = async (appId: number): Promise<void> => {
  const deadline = Date.now() + REGISTRATION_TIMEOUT_MS;
  while (!window.appStore.GetAppOverviewByAppID(appId)) {
    if (Date.now() >= deadline)
      return;
    await new Promise((resolve) => window.setTimeout(resolve, 100));
  }
};

interface ShortcutConfiguration {
  icon: string;
  launchOptions: string;
  launcherPath: string;
  name: string;
  startDirectory: string;
}

const applyShortcutConfiguration = (
  appId: number,
  profile: ShortcutConfiguration,
): void => {
  window.SteamClient.Apps.SetShortcutName(appId, profile.name);
  window.SteamClient.Apps.SetShortcutExe(appId, profile.launcherPath);
  window.SteamClient.Apps.SetShortcutStartDir(
    appId,
    profile.startDirectory,
  );
  window.SteamClient.Apps.SetShortcutLaunchOptions(
    appId,
    profile.launchOptions,
  );
  if (profile.icon.startsWith("/"))
    window.SteamClient.Apps.SetShortcutIcon(appId, profile.icon);
};

const ensureShortcut = async (
  profile: ShortcutConfiguration,
  existing: ShortcutOverview | undefined,
): Promise<number> => {
  const appId = existing?.appid ?? await window.SteamClient.Apps.AddShortcut(
    profile.name,
    profile.launcherPath,
    profile.startDirectory,
    profile.launchOptions,
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

export const ensureAppBridgeShortcut = async (
  profile: PreparedAppBridgeProfile,
  preferredAppId?: number,
): Promise<number> => {
  if (profile.error)
    throw new Error(profile.error);
  return ensureShortcut(
    {
      ...profile,
      launchOptions: profile.id,
    },
    findShortcutByNames(
      [profile.name, ...(profile.aliases ?? [])],
      preferredAppId,
    ),
  );
};

export const ensureSteamOsShortcut = async (
  profile: PreparedSteamOsApplication,
): Promise<number> => {
  if (profile.error)
    throw new Error(profile.error);
  return ensureShortcut(profile, findSteamOsShortcut(profile.aliases));
};
