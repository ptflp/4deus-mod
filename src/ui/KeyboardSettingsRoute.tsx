import { SidebarNavigation } from "@decky/ui";

import { useStrings } from "../core/localization";
import type { SettingsStore } from "../core/settings";
import { KeyboardPanel } from "../modules/keyboard/KeyboardPanel";

interface KeyboardSettingsRouteProps {
  settings: SettingsStore;
}

export const KeyboardSettingsRoute = ({
  settings,
}: KeyboardSettingsRouteProps) => {
  const strings = useStrings();

  return (
    <SidebarNavigation
      title="4deus Mod"
      showTitle
      pages={[
        {
          identifier: "keyboard",
          title: strings.keyboard,
          content: <KeyboardPanel settings={settings} />,
        },
      ]}
    />
  );
};
