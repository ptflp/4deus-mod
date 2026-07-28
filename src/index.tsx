import { callable, definePlugin, routerHook } from "@decky/api";
import { staticClasses } from "@decky/ui";
import { FaSlidersH } from "react-icons/fa";

import { ModuleHost } from "./core/module";
import { SettingsStore } from "./core/settings";
import type {
  AppBridgeApplication,
  AppBridgeProfileDraft,
  AppBridgeStatus,
  PreparedAppBridgeProfile,
} from "./modules/appBridge/types";
import { KeyboardFeature } from "./modules/keyboard/KeyboardFeature";
import { AppBridgeSettingsRoute } from "./ui/AppBridgeSettingsRoute";
import { KeyboardSettingsRoute } from "./ui/KeyboardSettingsRoute";
import {
  APP_BRIDGE_SETTINGS_ROUTE,
  KEYBOARD_SETTINGS_ROUTE,
  ModsPanel,
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
  routerHook.addRoute(KEYBOARD_SETTINGS_ROUTE, KeyboardRoute, {
    exact: true,
  });
  routerHook.addRoute(APP_BRIDGE_SETTINGS_ROUTE, AppBridgeRoute, {
    exact: true,
  });
  host.start();

  return {
    name: "4deus Mod",
    titleView: <div className={staticClasses.Title}>4deus Mod</div>,
    content: <ModsPanel settings={settings} />,
    icon: <FaSlidersH />,
    onDismount: () => {
      routerHook.removeRoute(APP_BRIDGE_SETTINGS_ROUTE);
      routerHook.removeRoute(KEYBOARD_SETTINGS_ROUTE);
      host.stop();
    },
  };
});
