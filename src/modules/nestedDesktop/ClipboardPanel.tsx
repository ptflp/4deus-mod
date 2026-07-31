import {
  PanelSection,
  PanelSectionRow,
  ToggleField,
} from "@decky/ui";
import { useEffect, useState } from "react";

import { useStrings } from "../../core/localization";
import type {
  NestedDesktopApi,
  NestedDesktopMouseStatus,
} from "./types";

interface ClipboardPanelProps {
  api: NestedDesktopApi;
}

export const ClipboardPanel = ({ api }: ClipboardPanelProps) => {
  const strings = useStrings();
  const [status, setStatus] = useState<NestedDesktopMouseStatus>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.getNestedDesktopMouseStatus()
      .then(setStatus)
      .catch((error) => {
        setMessage(error instanceof Error ? error.message : String(error));
      });
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
    <PanelSection title={strings.nestedDesktopClipboard}>
      <PanelSectionRow>
        <ToggleField
          label={strings.nestedDesktopClipboard}
          description={strings.nestedDesktopClipboardDescription}
          checked={status?.clipboardEnabled ?? false}
          disabled={busy || !status?.available}
          onChange={(enabled) => void update(
            () => api.setNestedDesktopClipboardEnabled(enabled),
          )}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label={strings.nestedDesktopClipboardFiles}
          description={strings.nestedDesktopClipboardFilesDescription}
          checked={status?.clipboardFilesEnabled ?? true}
          disabled={
            busy
            || !status?.available
            || !status.clipboardEnabled
          }
          onChange={(enabled) => void update(
            () => api.setNestedDesktopClipboardFilesEnabled(enabled),
          )}
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
