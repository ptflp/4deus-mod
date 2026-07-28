import { SidebarNavigation } from "@decky/ui";

import { useStrings } from "../core/localization";
import type { SettingsStore } from "../core/settings";
import { AppBridgePanel } from "../modules/appBridge/AppBridgePanel";
import type { AppBridgeApi } from "../modules/appBridge/types";

interface AppBridgeSettingsRouteProps {
  api: AppBridgeApi;
  settings: SettingsStore;
}

export const AppBridgeSettingsRoute = ({
  api,
  settings,
}: AppBridgeSettingsRouteProps) => {
  const strings = useStrings();

  return (
    <SidebarNavigation
      title="4deus Mod"
      showTitle
      pages={[
        {
          identifier: "app-bridge",
          title: strings.appBridge,
          content: <AppBridgePanel api={api} settings={settings} />,
        },
      ]}
    />
  );
};
