import {
  PanelSection,
  PanelSectionRow,
  ToggleField,
} from "@decky/ui";
import { useEffect, useState } from "react";

import { useStrings } from "../../core/localization";
import type {
  NestedDesktopMouseStatus,
  SystemToolsApi,
} from "./types";

interface RustDeskPanelProps {
  api: SystemToolsApi;
}

export const RustDeskPanel = ({ api }: RustDeskPanelProps) => {
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
    <PanelSection title="RustDesk">
      <PanelSectionRow>
        <ToggleField
          label={strings.rustDeskPointerFix}
          description={strings.rustDeskPointerFixDescription}
          checked={status?.rustDeskPointerFixEnabled ?? true}
          disabled={busy || !status?.available}
          onChange={(enabled) =>
            void update(() => api.setRustDeskPointerFixEnabled(enabled))}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label={strings.rustDeskScrollInertia}
          description={strings.rustDeskScrollInertiaDescription}
          checked={status?.rustDeskScrollInertiaEnabled ?? false}
          disabled={
            busy
            || !status?.available
            || !status.rustDeskPointerFixEnabled
          }
          onChange={(enabled) =>
            void update(
              () => api.setRustDeskScrollInertiaEnabled(enabled),
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
