import {
  DialogButton,
  PanelSection,
  PanelSectionRow,
  SliderField,
} from "@decky/ui";
import { useEffect, useState } from "react";

import { useStrings } from "../../core/localization";
import type {
  NestedDesktopMouseStatus,
  TouchscreenInertiaConfig,
} from "./types";

const DEFAULT_CONFIG: TouchscreenInertiaConfig = {
  durationMs: 600,
  startSpeed: 420,
  minDistance: 36,
};

interface TouchscreenInertiaAdvancedPanelProps {
  busy: boolean;
  onApply(config: TouchscreenInertiaConfig): Promise<void>;
  status?: NestedDesktopMouseStatus;
}

export const TouchscreenInertiaAdvancedPanel = ({
  busy,
  onApply,
  status,
}: TouchscreenInertiaAdvancedPanelProps) => {
  const strings = useStrings();
  const [draft, setDraft] =
    useState<TouchscreenInertiaConfig>(DEFAULT_CONFIG);
  const config = status?.touchInertiaConfig;

  useEffect(() => {
    if (config)
      setDraft(config);
  }, [
    config?.durationMs,
    config?.startSpeed,
    config?.minDistance,
  ]);

  const disabled = (
    busy
    || !status?.available
    || !status.touchAvailable
    || !status.touchEnabled
    || !status.touchInertiaEnabled
  );
  const changed = Boolean(
    config
    && (
      draft.durationMs !== config.durationMs
      || draft.startSpeed !== config.startSpeed
      || draft.minDistance !== config.minDistance
    )
  );

  return (
    <PanelSection title={strings.nestedDesktopTouchInertiaTuning}>
      <PanelSectionRow>
        <SliderField
          label={strings.nestedDesktopTouchInertiaDuration}
          description={
            strings.nestedDesktopTouchInertiaDurationDescription
          }
          value={draft.durationMs}
          min={150}
          max={1200}
          step={50}
          resetValue={DEFAULT_CONFIG.durationMs}
          showValue
          valueSuffix=" ms"
          validValues="range"
          disabled={disabled}
          onChange={(durationMs) =>
            setDraft({ ...draft, durationMs })}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <SliderField
          label={strings.nestedDesktopTouchInertiaStartSpeed}
          description={
            strings.nestedDesktopTouchInertiaStartSpeedDescription
          }
          value={draft.startSpeed}
          min={180}
          max={1200}
          step={30}
          resetValue={DEFAULT_CONFIG.startSpeed}
          showValue
          valueSuffix=" px/s"
          validValues="range"
          disabled={disabled}
          onChange={(startSpeed) =>
            setDraft({ ...draft, startSpeed })}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <SliderField
          label={strings.nestedDesktopTouchInertiaMinDistance}
          description={
            strings.nestedDesktopTouchInertiaMinDistanceDescription
          }
          value={draft.minDistance}
          min={16}
          max={120}
          step={4}
          resetValue={DEFAULT_CONFIG.minDistance}
          showValue
          valueSuffix=" px"
          validValues="range"
          disabled={disabled}
          onChange={(minDistance) =>
            setDraft({ ...draft, minDistance })}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <div style={{ display: "flex", gap: "8px", width: "100%" }}>
          <DialogButton
            disabled={disabled || !changed}
            onClick={() => void onApply(draft)}
            style={{ flex: 1 }}
          >
            {strings.applyAdvancedSettings}
          </DialogButton>
          <DialogButton
            disabled={disabled}
            onClick={() => {
              setDraft(DEFAULT_CONFIG);
              void onApply(DEFAULT_CONFIG);
            }}
            style={{ flex: 1 }}
          >
            {strings.resetAdvancedSettings}
          </DialogButton>
        </div>
      </PanelSectionRow>
    </PanelSection>
  );
};
