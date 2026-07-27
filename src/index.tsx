import { definePlugin } from "@decky/api";
import { staticClasses } from "@decky/ui";
import { FaSlidersH } from "react-icons/fa";

import { ModuleHost } from "./core/module";
import { SettingsStore } from "./core/settings";
import { KeyboardFeature } from "./modules/keyboard/KeyboardFeature";
import { KeyboardPanel } from "./modules/keyboard/KeyboardPanel";

export default definePlugin(() => {
  const settings = new SettingsStore();
  const host = new ModuleHost([
    new KeyboardFeature(settings),
  ]);
  host.start();

  return {
    name: "4deus Mod",
    titleView: <div className={staticClasses.Title}>4deus Mod</div>,
    content: <KeyboardPanel settings={settings} />,
    icon: <FaSlidersH />,
    onDismount: () => host.stop(),
  };
});
