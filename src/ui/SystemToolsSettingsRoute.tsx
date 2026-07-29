import { SidebarNavigation } from "@decky/ui";

import { useStrings } from "../core/localization";
import { SystemToolsPanel } from "../modules/systemTools/SystemToolsPanel";
import type { SystemToolsApi } from "../modules/systemTools/types";

interface SystemToolsSettingsRouteProps {
  api: SystemToolsApi;
}

export const SystemToolsSettingsRoute = ({
  api,
}: SystemToolsSettingsRouteProps) => {
  const strings = useStrings();

  return (
    <SidebarNavigation
      title="4deus Mod"
      showTitle
      pages={[
        {
          identifier: "system-tools",
          title: strings.systemTools,
          content: <SystemToolsPanel api={api} />,
        },
      ]}
    />
  );
};
