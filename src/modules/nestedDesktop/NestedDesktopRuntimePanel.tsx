import {
  PanelSection,
  PanelSectionRow,
  ToggleField,
} from "@decky/ui";
import { useEffect, useState } from "react";

import { useStrings } from "../../core/localization";
import type { SettingsStore } from "../../core/settings";
import { AdvancedSettings } from "../../ui/AdvancedSettings";
import {
  TouchscreenInertiaAdvancedPanel,
} from "./TouchscreenInertiaAdvancedPanel";
import type {
  NestedDesktopApi,
  NestedDesktopMouseStatus,
  TouchscreenInertiaConfig,
} from "./types";

interface NestedDesktopRuntimePanelProps {
  api: NestedDesktopApi;
  settings?: SettingsStore;
  showBindings?: boolean;
}

export const NestedDesktopRuntimePanel = ({
  api,
  settings,
  showBindings = false,
}: NestedDesktopRuntimePanelProps) => {
  const strings = useStrings();
  const [status, setStatus] = useState<NestedDesktopMouseStatus>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.getNestedDesktopMouseStatus()
      .then(setStatus)
      .catch((error) => setMessage(
        error instanceof Error ? error.message : String(error),
      ));
  }, []);

  const update = async (
    action: () => Promise<NestedDesktopMouseStatus>,
  ): Promise<void> => {
    setBusy(true);
    setMessage("");
    try {
      const nextStatus = await action();
      setStatus(nextStatus);
      if (nextStatus.error)
        setMessage(nextStatus.error);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PanelSection title="Nested Desktop">
        <PanelSectionRow>
          <ToggleField
            label={strings.nestedDesktopMouseBridge}
            description={strings.nestedDesktopMouseBridgeDescription}
            checked={status?.enabled ?? false}
            disabled={busy || !status?.available}
            onChange={(enabled) => void update(
              () => api.setNestedDesktopMouseEnabled(enabled),
            )}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label={strings.nestedDesktopTouchscreen}
            description={strings.nestedDesktopTouchscreenDescription}
            checked={status?.touchEnabled ?? true}
            disabled={
              busy
              || !status?.available
              || !status.touchAvailable
            }
            onChange={(enabled) => void update(
              () => api.setNestedDesktopTouchEnabled(enabled),
            )}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label={strings.nestedDesktopTouchInertia}
            description={strings.nestedDesktopTouchInertiaDescription}
            checked={status?.touchInertiaEnabled ?? true}
            disabled={
              busy
              || !status?.available
              || !status.touchAvailable
              || !status.touchEnabled
            }
            onChange={(enabled) => void update(
              () => api.setNestedDesktopTouchInertiaEnabled(enabled),
            )}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label={strings.nestedDesktopTrackpadInertia}
            description={strings.nestedDesktopTrackpadInertiaDescription}
            checked={status?.inertiaEnabled ?? true}
            disabled={
              busy
              || !status?.available
              || !status.enabled
            }
            onChange={(enabled) => void update(
              () => api.setNestedDesktopMouseInertiaEnabled(enabled),
            )}
          />
        </PanelSectionRow>
      </PanelSection>

      {settings && (
        <AdvancedSettings
          label={strings.advancedSettings}
          description={strings.advancedSettingsDescription}
          moduleId="nestedDesktop"
          settings={settings}
        >
          <TouchscreenInertiaAdvancedPanel
            busy={busy}
            status={status}
            onApply={async (
              config: TouchscreenInertiaConfig,
            ): Promise<void> => {
              await update(
                () => api.setNestedDesktopTouchInertiaConfig(
                  config.durationMs,
                  config.startSpeed,
                  config.minDistance,
                ),
              );
            }}
          />
        </AdvancedSettings>
      )}

      {showBindings && (
        <PanelSection title={strings.nestedDesktopHotkeys}>
          <PanelSectionRow>
            <ToggleField
              label={strings.nestedDesktopHotkeysEnabled}
              description={strings.nestedDesktopHotkeysEnabledDescription}
              checked={status?.bindingsEnabled ?? true}
              disabled={busy || !status?.available}
              onChange={(enabled) => void update(
                () => api.setNestedDesktopBindingsEnabled(enabled),
              )}
            />
          </PanelSectionRow>
        </PanelSection>
      )}

      {message && (
        <PanelSection>
          <PanelSectionRow>
            <div>{message}</div>
          </PanelSectionRow>
        </PanelSection>
      )}
    </>
  );
};
