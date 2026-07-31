import {
  DialogButton,
  Focusable,
  Navigation,
  staticClasses,
} from "@decky/ui";
import { FaCog } from "react-icons/fa";

import { useStrings } from "../core/localization";
import { PLUGIN_SETTINGS_ROUTE } from "./routes";

export const PluginTitle = () => {
  const strings = useStrings();

  const openSettings = (): void => {
    Navigation.Navigate(PLUGIN_SETTINGS_ROUTE);
    Navigation.CloseSideMenus();
  };

  return (
    <Focusable
      className={staticClasses.Title}
      style={{
        alignItems: "center",
        display: "flex",
        gap: "10px",
        justifyContent: "space-between",
        width: "100%",
      }}
      children={(
        <>
          <div>4deus Mod</div>
          <DialogButton
            aria-label={strings.pluginSettings}
            onClick={openSettings}
            style={{
              alignItems: "center",
              display: "flex",
              justifyContent: "center",
              minHeight: "36px",
              minWidth: "36px",
              padding: "7px",
              width: "36px",
            }}
          >
            <FaCog />
          </DialogButton>
        </>
      )}
    />
  );
};
