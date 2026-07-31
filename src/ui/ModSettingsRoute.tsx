import {
  SidebarNavigation,
  type SidebarNavigationPage,
} from "@decky/ui";

import { useStrings } from "../core/localization";
import type { SettingsStore } from "../core/settings";
import { AppBridgePanel } from "../modules/appBridge/AppBridgePanel";
import {
  AppBridgePopularPanel,
} from "../modules/appBridge/AppBridgePopularPanel";
import type { AppBridgeApi } from "../modules/appBridge/types";
import { ControllerPanel } from "../modules/controller/ControllerPanel";
import type { ControllerApi } from "../modules/controller/types";
import { DeveloperModePanel } from "../modules/developer/DeveloperModePanel";
import { TrackpadMetricsPanel } from "../modules/developer/TrackpadMetricsPanel";
import type { DeveloperApi } from "../modules/developer/types";
import { KeyboardPanel } from "../modules/keyboard/KeyboardPanel";
import { ClipboardPanel } from "../modules/nestedDesktop/ClipboardPanel";
import {
  KeyboardShortcutsPanel,
} from "../modules/keyboard/KeyboardShortcutsPanel";
import {
  MangoHudPanel,
} from "../modules/nestedDesktop/MangoHudPanel";
import {
  NestedDesktopBindingsPanel,
} from "../modules/nestedDesktop/NestedDesktopBindingsPanel";
import {
  NestedDesktopPanel,
} from "../modules/nestedDesktop/NestedDesktopPanel";
import { RustDeskPanel } from "../modules/nestedDesktop/RustDeskPanel";
import type {
  MangoHudApi,
  NestedDesktopApi,
} from "../modules/nestedDesktop/types";

interface ModSettingsRouteProps {
  appBridgeApi: AppBridgeApi;
  controllerApi: ControllerApi;
  developerApi: DeveloperApi;
  initialPage: string;
  mangoHudApi: MangoHudApi;
  nestedDesktopApi: NestedDesktopApi;
  settings: SettingsStore;
}

export const ModSettingsRoute = ({
  appBridgeApi,
  controllerApi,
  developerApi,
  initialPage,
  mangoHudApi,
  nestedDesktopApi,
  settings,
}: ModSettingsRouteProps) => {
  const strings = useStrings();
  let pages: SidebarNavigationPage[];

  switch (initialPage) {
  case "keyboard":
    pages = [
      {
        identifier: "keyboard",
        title: strings.keyboard,
        content: <KeyboardPanel settings={settings} />,
      },
      {
        identifier: "keyboard-hotkeys",
        title: strings.hotkeys,
        content: <KeyboardShortcutsPanel settings={settings} />,
      },
    ];
    break;
  case "controller":
    pages = [
      {
        identifier: "controller",
        title: strings.controller,
        content: <ControllerPanel api={controllerApi} />,
      },
      {
        identifier: "trackpad-metrics",
        title: strings.trackpadMetrics,
        content: <TrackpadMetricsPanel api={developerApi} />,
      },
    ];
    break;
  case "nested-desktop":
    pages = [
      {
        identifier: "nested-desktop",
        title: "Nested Desktop",
        content: (
          <NestedDesktopPanel
            api={nestedDesktopApi}
            settings={settings}
          />
        ),
      },
      {
        identifier: "nested-desktop-clipboard",
        title: strings.nestedDesktopClipboard,
        content: <ClipboardPanel api={nestedDesktopApi} />,
      },
      {
        identifier: "nested-desktop-hotkeys",
        title: strings.nestedDesktopHotkeys,
        content: <NestedDesktopBindingsPanel api={nestedDesktopApi} />,
      },
      {
        identifier: "rustdesk",
        title: "RustDesk",
        content: <RustDeskPanel api={nestedDesktopApi} />,
      },
      {
        identifier: "mangohud",
        title: "MangoHud",
        content: <MangoHudPanel api={mangoHudApi} />,
      },
    ];
    break;
  case "app-bridge":
    pages = [
      {
        identifier: "app-bridge",
        title: strings.appBridge,
        content: <AppBridgePanel api={appBridgeApi} settings={settings} />,
      },
      {
        identifier: "app-bridge-popular",
        title: "Popular",
        content: (
          <AppBridgePopularPanel api={appBridgeApi} settings={settings} />
        ),
      },
    ];
    break;
  default:
    pages = [{
      identifier: "plugin-settings",
      title: strings.pluginSettings,
      content: <DeveloperModePanel api={developerApi} />,
    }];
  }

  return (
    <SidebarNavigation
      title="4deus Mod"
      showTitle
      pages={pages}
    />
  );
};
