import {
  addEventListener,
  callable,
  definePlugin,
  removeEventListener,
  routerHook,
} from "@decky/api";
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
import type {
  DeveloperApi,
  DeveloperSettingsStatus,
  TrackpadMetricsWindow,
} from "./modules/developer/types";
import { KeyboardFeature } from "./modules/keyboard/KeyboardFeature";
import type {
  NestedDesktopBindingAction,
  NestedDesktopBindingSource,
} from "./modules/systemTools/nestedDesktopBindings";
import type {
  MangoHudFixStatus,
  ControllerStatus,
  NestedDesktopMouseStatus,
  PreparedSteamOsApplication,
  SteamOsApplicationStatus,
  SteamOsArtworkResult,
  SystemToolsApi,
} from "./modules/systemTools/types";
import { AppBridgeSettingsRoute } from "./ui/AppBridgeSettingsRoute";
import { KeyboardSettingsRoute } from "./ui/KeyboardSettingsRoute";
import {
  PLUGIN_SETTINGS_ROUTE,
  PluginSettingsRoute,
} from "./ui/PluginSettingsRoute";
import { PluginTitle } from "./ui/PluginTitle";
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
  const setNestedDesktopKeyboardVisible = callable<[boolean], boolean>(
    "set_nested_desktop_keyboard_visible",
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
    getNestedDesktopMouseStatus: callable<[], NestedDesktopMouseStatus>(
      "get_nested_desktop_mouse_status",
    ),
    setNestedDesktopMouseEnabled: callable<
      [boolean],
      NestedDesktopMouseStatus
    >("set_nested_desktop_mouse_enabled"),
    setNestedDesktopMouseInertiaEnabled: callable<
      [boolean],
      NestedDesktopMouseStatus
    >("set_nested_desktop_mouse_inertia_enabled"),
    setRustDeskPointerFixEnabled: callable<
      [boolean],
      NestedDesktopMouseStatus
    >("set_rustdesk_pointer_fix_enabled"),
    setRustDeskFocusOnInputEnabled: callable<
      [boolean],
      NestedDesktopMouseStatus
    >("set_rustdesk_focus_on_input_enabled"),
    setRustDeskScrollInertiaEnabled: callable<
      [boolean],
      NestedDesktopMouseStatus
    >("set_rustdesk_scroll_inertia_enabled"),
    setNestedDesktopBindingsEnabled: callable<
      [boolean],
      NestedDesktopMouseStatus
    >("set_nested_desktop_bindings_enabled"),
    setNestedDesktopBinding: callable<
      [NestedDesktopBindingSource, NestedDesktopBindingAction],
      NestedDesktopMouseStatus
    >("set_nested_desktop_binding"),
    resetNestedDesktopBindings: callable<
      [],
      NestedDesktopMouseStatus
    >("reset_nested_desktop_bindings"),
    getControllerStatus: callable<[], ControllerStatus>(
      "get_controller_status",
    ),
    setTrackpadAutoRecoveryEnabled: callable<
      [boolean],
      ControllerStatus
    >("set_trackpad_auto_recovery_enabled"),
  };
  const developerApi: DeveloperApi = {
    getStatus: callable<[], DeveloperSettingsStatus>(
      "get_developer_settings_status",
    ),
    setDeveloperMode: callable<[boolean], DeveloperSettingsStatus>(
      "set_developer_mode",
    ),
    setTrackpadMetricsEnabled: callable<
      [boolean],
      DeveloperSettingsStatus
    >("set_trackpad_metrics_enabled"),
    getTrackpadMetricsWindow: callable<
      [string, number],
      TrackpadMetricsWindow
    >("get_trackpad_metrics_window"),
    captureTrackpadMetrics: callable<[], DeveloperSettingsStatus>(
      "capture_trackpad_metrics",
    ),
    clearTrackpadMetricsBuffer: callable<[], DeveloperSettingsStatus>(
      "clear_trackpad_metrics_buffer",
    ),
    deleteTrackpadMetricsCapture: callable<
      [string],
      DeveloperSettingsStatus
    >("delete_trackpad_metrics_capture"),
  };
  const keyboardFeature = new KeyboardFeature(
    settings,
    sendSystemKey,
    setSystemKeyState,
    logKeyboardDiagnostics,
    setNestedDesktopKeyboardVisible,
  );
  const host = new ModuleHost([keyboardFeature]);
  const nestedDesktopActionListener = addEventListener<[string]>(
    "nested_desktop_action",
    (action) => {
      if (action === "SHOW_KEYBOARD")
        keyboardFeature.showKeyboard();
      else if (action === "HIDE_KEYBOARD")
        keyboardFeature.hideKeyboard();
    },
  );
  const KeyboardRoute = () => <KeyboardSettingsRoute settings={settings} />;
  const AppBridgeRoute = () => (
    <AppBridgeSettingsRoute api={appBridgeApi} settings={settings} />
  );
  const SystemToolsRoute = () => (
    <SystemToolsSettingsRoute api={systemToolsApi} />
  );
  const PluginSettings = () => (
    <PluginSettingsRoute api={developerApi} />
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
  routerHook.addRoute(PLUGIN_SETTINGS_ROUTE, PluginSettings, {
    exact: true,
  });
  host.start();

  return {
    name: "4deus Mod",
    titleView: <PluginTitle />,
    content: <ModsPanel settings={settings} />,
    icon: <FaSlidersH />,
    onDismount: () => {
      removeEventListener(
        "nested_desktop_action",
        nestedDesktopActionListener,
      );
      routerHook.removeRoute(PLUGIN_SETTINGS_ROUTE);
      routerHook.removeRoute(SYSTEM_TOOLS_SETTINGS_ROUTE);
      routerHook.removeRoute(APP_BRIDGE_SETTINGS_ROUTE);
      routerHook.removeRoute(KEYBOARD_SETTINGS_ROUTE);
      host.stop();
    },
  };
});
