import {
  DialogButton,
  PanelSection,
  PanelSectionRow,
} from "@decky/ui";

import { useStrings } from "../../core/localization";
import type { SettingsStore } from "../../core/settings";
import type { AppBridgeApi } from "./types";
import { useAppBridgeInstaller } from "./useAppBridgeInstaller";

interface AppBridgePopularPanelProps {
  api: AppBridgeApi;
  settings: SettingsStore;
}

export const AppBridgePopularPanel = ({
  api,
  settings,
}: AppBridgePopularPanelProps) => {
  const strings = useStrings();
  const installer = useAppBridgeInstaller(api, settings, strings);

  return (
    <PanelSection title={strings.appBridgeQuickSetup}>
      <PanelSectionRow>
        <div>{strings.appBridgeChromeDescription}</div>
      </PanelSectionRow>
      <PanelSectionRow>
        <DialogButton
          disabled={installer.busy}
          onClick={() => void installer.install(() => api.prepareChrome())}
          style={{ width: "100%" }}
        >
          {strings.addOrFixChrome}
        </DialogButton>
      </PanelSectionRow>
      <PanelSectionRow>
        <div>{strings.appBridgeParsecDescription}</div>
      </PanelSectionRow>
      <PanelSectionRow>
        <DialogButton
          disabled={installer.busy}
          onClick={() => void installer.install(() => api.prepareParsec())}
          style={{ width: "100%" }}
        >
          {strings.addOrFixParsec}
        </DialogButton>
      </PanelSectionRow>
      <PanelSectionRow>
        <div>{strings.appBridgeRustDeskDescription}</div>
      </PanelSectionRow>
      <PanelSectionRow>
        <DialogButton
          disabled={installer.busy}
          onClick={() => void installer.install(() => api.prepareRustDesk())}
          style={{ width: "100%" }}
        >
          {strings.addOrFixRustDesk}
        </DialogButton>
      </PanelSectionRow>
      <PanelSectionRow>
        <div>{strings.appBridgeTerminalDescription}</div>
      </PanelSectionRow>
      <PanelSectionRow>
        <DialogButton
          disabled={installer.busy}
          onClick={() => void installer.install(() => api.prepareTerminal())}
          style={{ width: "100%" }}
        >
          {strings.addOrFixTerminal}
        </DialogButton>
      </PanelSectionRow>
      {installer.message && (
        <PanelSectionRow>
          <div>{installer.message}</div>
        </PanelSectionRow>
      )}
    </PanelSection>
  );
};
