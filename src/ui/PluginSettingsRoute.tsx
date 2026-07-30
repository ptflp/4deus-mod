import { SidebarNavigation } from "@decky/ui";
import { FaCode, FaWaveSquare } from "react-icons/fa";

import { useStrings } from "../core/localization";
import { DeveloperModePanel } from "../modules/developer/DeveloperModePanel";
import { TrackpadMetricsPanel } from "../modules/developer/TrackpadMetricsPanel";
import type { DeveloperApi } from "../modules/developer/types";

export const PLUGIN_SETTINGS_ROUTE = "/4deus-mod/settings";

interface PluginSettingsRouteProps {
  api: DeveloperApi;
}

export const PluginSettingsRoute = ({
  api,
}: PluginSettingsRouteProps) => {
  const strings = useStrings();

  return (
    <SidebarNavigation
      title="4deus Mod"
      showTitle
      pages={[
        {
          identifier: "plugin-settings",
          title: strings.pluginSettings,
          icon: <FaCode />,
          content: <DeveloperModePanel api={api} />,
        },
        {
          identifier: "trackpad-metrics",
          title: strings.trackpadMetrics,
          icon: <FaWaveSquare />,
          content: <TrackpadMetricsPanel api={api} />,
        },
      ]}
    />
  );
};
