import {
  DialogButton,
  Field,
  Focusable,
  Navigation,
  PanelSection,
  Toggle,
} from "@decky/ui";
import { useSyncExternalStore } from "react";
import { FaCog, FaKeyboard, FaProjectDiagram } from "react-icons/fa";

import { useStrings } from "../core/localization";
import type { SettingsStore } from "../core/settings";

export const KEYBOARD_SETTINGS_ROUTE = "/4deus-mod/keyboard";
export const APP_BRIDGE_SETTINGS_ROUTE = "/4deus-mod/app-bridge";

interface ModsPanelProps {
  settings: SettingsStore;
}

const openSettings = (route: string): void => {
  Navigation.Navigate(route);
  Navigation.CloseSideMenus();
};

export const ModsPanel = ({ settings }: ModsPanelProps) => {
  const strings = useStrings();
  const snapshot = useSyncExternalStore(
    settings.subscribe,
    settings.getSnapshot,
  );

  return (
    <PanelSection title="4deus Mod">
      <Field
        label={strings.keyboard}
        description={strings.enabledDescription}
        icon={<FaKeyboard />}
        childrenLayout="inline"
        childrenContainerWidth="max"
        inlineWrap="keep-inline"
        verticalAlignment="center"
      >
        <Focusable
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
          children={(
            <>
              <Toggle
                value={snapshot.keyboard.enabled}
                onChange={(enabled) => settings.updateKeyboard({ enabled })}
              />
              <DialogButton
                aria-label={strings.keyboard}
                onClick={() => openSettings(KEYBOARD_SETTINGS_ROUTE)}
                style={{
                  alignItems: "center",
                  display: "flex",
                  justifyContent: "center",
                  minHeight: "40px",
                  minWidth: "40px",
                  padding: "8px",
                  width: "40px",
                }}
              >
                <FaCog />
              </DialogButton>
            </>
          )}
        />
      </Field>
      <Field
        label={strings.appBridge}
        description={strings.appBridgeEnabledDescription}
        icon={<FaProjectDiagram />}
        childrenLayout="inline"
        childrenContainerWidth="max"
        inlineWrap="keep-inline"
        verticalAlignment="center"
      >
        <Focusable
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
          children={(
            <>
              <Toggle
                value={snapshot.appBridge.enabled}
                onChange={(enabled) => settings.updateAppBridge({ enabled })}
              />
              <DialogButton
                aria-label={strings.appBridge}
                onClick={() => openSettings(APP_BRIDGE_SETTINGS_ROUTE)}
                style={{
                  alignItems: "center",
                  display: "flex",
                  justifyContent: "center",
                  minHeight: "40px",
                  minWidth: "40px",
                  padding: "8px",
                  width: "40px",
                }}
              >
                <FaCog />
              </DialogButton>
            </>
          )}
        />
      </Field>
    </PanelSection>
  );
};
