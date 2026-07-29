import { callable, definePlugin, routerHook } from "@decky/api";
import { staticClasses } from "@decky/ui";
import { FaSlidersH } from "react-icons/fa";

import { ModuleHost } from "./core/module";
import { SettingsStore } from "./core/settings";
import type {
  AppBridgeApplication,
  AppBridgeArtworkResult,
  AppBridgeProfileDraft,
  AppBridgeStatus,
  PreparedAppBridgeProfile,
} from "./modules/appBridge/types";
import { KeyboardFeature } from "./modules/keyboard/KeyboardFeature";
import type {
  MangoHudFixStatus,
  PreparedSteamOsApplication,
  SteamOsApplicationStatus,
  SteamOsArtworkResult,
  SystemToolsApi,
} from "./modules/systemTools/types";
import { AppBridgeSettingsRoute } from "./ui/AppBridgeSettingsRoute";
import { KeyboardSettingsRoute } from "./ui/KeyboardSettingsRoute";
import { SystemToolsSettingsRoute } from "./ui/SystemToolsSettingsRoute";
import {
  APP_BRIDGE_SETTINGS_ROUTE,
  KEYBOARD_SETTINGS_ROUTE,
  ModsPanel,
  SYSTEM_TOOLS_SETTINGS_ROUTE,
} from "./ui/ModsPanel";

export default definePlugin(() => {
  const settings = new SettingsStore();
  const sendSystemKey = callable<
    [string, boolean, boolean, boolean, boolean],
    boolean
  >(
    "send_system_key",
  );
  const setSystemKeyState = callable<[string, boolean], boolean>(
    "set_system_key_state",
  );
  const logKeyboardDiagnostics = callable<[string], boolean>(
    "log_keyboard_diagnostics",
  );
  const appBridgeApi = {
    getStatus: callable<[], AppBridgeStatus>("get_app_bridge_status"),
    installArtwork: callable<
      [string, number],
      AppBridgeArtworkResult
    >("install_app_bridge_artwork"),
    listApplications: callable<[], AppBridgeApplication[]>(
      "list_app_bridge_applications",
    ),
    prepareParsec: callable<[], PreparedAppBridgeProfile>(
      "prepare_parsec_app_bridge",
    ),
    prepareRustDesk: callable<[], PreparedAppBridgeProfile>(
      "prepare_rustdesk_app_bridge",
    ),
    saveProfile: callable<
      [AppBridgeProfileDraft],
      PreparedAppBridgeProfile
    >("save_app_bridge_profile"),
  };
  const systemToolsApi: SystemToolsApi = {
    getMangoHudFixStatus: callable<[], MangoHudFixStatus>(
      "get_mangohud_fix_status",
    ),
    installMangoHudFix: callable<[], MangoHudFixStatus>(
      "install_mangohud_fix",
    ),
    removeMangoHudFix: callable<[], MangoHudFixStatus>(
      "remove_mangohud_fix",
    ),
    getSteamOsApplicationStatus: callable<[], SteamOsApplicationStatus>(
      "get_steamos_application_status",
    ),
    prepareSteamOsApplication: callable<[], PreparedSteamOsApplication>(
      "prepare_steamos_application",
    ),
    installSteamOsApplicationArtwork: callable<
      [number],
      SteamOsArtworkResult
    >("install_steamos_application_artwork"),
  };
  const host = new ModuleHost([
    new KeyboardFeature(
      settings,
      sendSystemKey,
      setSystemKeyState,
      logKeyboardDiagnostics,
    ),
  ]);
  const KeyboardRoute = () => <KeyboardSettingsRoute settings={settings} />;
  const AppBridgeRoute = () => (
    <AppBridgeSettingsRoute api={appBridgeApi} settings={settings} />
  );
  const SystemToolsRoute = () => (
    <SystemToolsSettingsRoute api={systemToolsApi} />
  );
  routerHook.addRoute(KEYBOARD_SETTINGS_ROUTE, KeyboardRoute, {
    exact: true,
  });
  routerHook.addRoute(APP_BRIDGE_SETTINGS_ROUTE, AppBridgeRoute, {
    exact: true,
  });
  routerHook.addRoute(SYSTEM_TOOLS_SETTINGS_ROUTE, SystemToolsRoute, {
    exact: true,
  });
  host.start();

  return {
    name: "4deus Mod",
    titleView: <div className={staticClasses.Title}>4deus Mod</div>,
    content: <ModsPanel settings={settings} />,
    icon: <FaSlidersH />,
    onDismount: () => {
      routerHook.removeRoute(SYSTEM_TOOLS_SETTINGS_ROUTE);
      routerHook.removeRoute(APP_BRIDGE_SETTINGS_ROUTE);
      routerHook.removeRoute(KEYBOARD_SETTINGS_ROUTE);
      host.stop();
    },
  };
});
