import { callable, definePlugin, routerHook } from "@decky/api";
import { staticClasses } from "@decky/ui";
import { FaSlidersH } from "react-icons/fa";

import { ModuleHost } from "./core/module";
import { SettingsStore } from "./core/settings";
import { KeyboardFeature } from "./modules/keyboard/KeyboardFeature";
import { KeyboardSettingsRoute } from "./ui/KeyboardSettingsRoute";
import { KEYBOARD_SETTINGS_ROUTE, ModsPanel } from "./ui/ModsPanel";

export default definePlugin(() => {
  const settings = new SettingsStore();
  const sendSystemKey = callable<[string, boolean, boolean], boolean>(
    "send_system_key",
  );
  const host = new ModuleHost([
    new KeyboardFeature(settings, sendSystemKey),
  ]);
  const KeyboardRoute = () => <KeyboardSettingsRoute settings={settings} />;
  routerHook.addRoute(KEYBOARD_SETTINGS_ROUTE, KeyboardRoute, {
    exact: true,
  });
  host.start();

  return {
    name: "4deus Mod",
    titleView: <div className={staticClasses.Title}>4deus Mod</div>,
    content: <ModsPanel settings={settings} />,
    icon: <FaSlidersH />,
    onDismount: () => {
      routerHook.removeRoute(KEYBOARD_SETTINGS_ROUTE);
      host.stop();
    },
  };
});
