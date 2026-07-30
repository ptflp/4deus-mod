import {
  PanelSection,
  PanelSectionRow,
  ToggleField,
} from "@decky/ui";
import { useEffect, useState } from "react";

import { useStrings } from "../../core/localization";
import type {
  DeveloperApi,
  DeveloperSettingsStatus,
} from "./types";

interface DeveloperModePanelProps {
  api: DeveloperApi;
}

const errorText = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

export const DeveloperModePanel = ({ api }: DeveloperModePanelProps) => {
  const strings = useStrings();
  const [status, setStatus] = useState<DeveloperSettingsStatus>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    api.getStatus()
      .then((nextStatus) => {
        if (active)
          setStatus(nextStatus);
      })
      .catch((error) => {
        if (active)
          setMessage(errorText(error));
      });
    return () => {
      active = false;
    };
  }, [api]);

  const setDeveloperMode = async (enabled: boolean): Promise<void> => {
    setBusy(true);
    setMessage("");
    try {
      const nextStatus = await api.setDeveloperMode(enabled);
      setStatus(nextStatus);
      setMessage(nextStatus.error ?? "");
    } catch (error) {
      setMessage(errorText(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <PanelSection title={strings.pluginSettings}>
      <PanelSectionRow>
        <ToggleField
          label={strings.developerMode}
          description={strings.developerModeDescription}
          checked={status?.developerMode ?? false}
          disabled={busy || !status}
          onChange={(enabled) => void setDeveloperMode(enabled)}
        />
      </PanelSectionRow>
      {!status && !message && (
        <PanelSectionRow>
          <div>{strings.systemToolsLoading}</div>
        </PanelSectionRow>
      )}
      {message && (
        <PanelSectionRow>
          <div>{message}</div>
        </PanelSectionRow>
      )}
    </PanelSection>
  );
};
