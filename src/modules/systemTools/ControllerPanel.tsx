import {
  PanelSection,
  PanelSectionRow,
  ToggleField,
} from "@decky/ui";
import { useEffect, useState } from "react";

import { useStrings } from "../../core/localization";
import type {
  ControllerStatus,
  SystemToolsApi,
} from "./types";

interface ControllerPanelProps {
  api: SystemToolsApi;
}

export const ControllerPanel = ({ api }: ControllerPanelProps) => {
  const strings = useStrings();
  const [status, setStatus] = useState<ControllerStatus>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.getControllerStatus()
      .then((nextStatus) => {
        setStatus(nextStatus);
        if (nextStatus.error)
          setMessage(nextStatus.error);
      })
      .catch((error) => {
        setMessage(error instanceof Error ? error.message : String(error));
      });
  }, []);

  const setEnabled = async (enabled: boolean): Promise<void> => {
    setBusy(true);
    setMessage("");
    try {
      const nextStatus =
        await api.setTrackpadAutoRecoveryEnabled(enabled);
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
    <PanelSection title={strings.controller}>
      <PanelSectionRow>
        <ToggleField
          label={strings.trackpadAutoRecovery}
          description={strings.trackpadAutoRecoveryDescription}
          checked={status?.autoRecoveryEnabled ?? true}
          disabled={busy || status?.available === false}
          onChange={(enabled) => void setEnabled(enabled)}
        />
      </PanelSectionRow>
      {message && (
        <PanelSectionRow>
          <div>{message}</div>
        </PanelSectionRow>
      )}
    </PanelSection>
  );
};
