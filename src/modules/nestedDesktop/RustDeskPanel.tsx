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

interface RustDeskPanelProps {
  api: NestedDesktopApi;
}

export const RustDeskPanel = ({ api }: RustDeskPanelProps) => {
  const strings = useStrings();
  const [status, setStatus] = useState<NestedDesktopMouseStatus>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const flatpakUnsupported = status?.rustDeskFlatpakInstalled ?? false;

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
      if (nextStatus.errorCode === "rustdesk_flatpak_unsupported")
        setMessage(strings.rustDeskFlatpakUnsupported);
      else if (nextStatus.error)
        setMessage(nextStatus.error);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <PanelSection title="RustDesk">
      {(flatpakUnsupported || message) && (
        <PanelSectionRow>
          <div
            role="alert"
            style={{
              color: "#ff5c5c",
              fontWeight: 600,
              lineHeight: 1.35,
            }}
          >
            {flatpakUnsupported
              ? strings.rustDeskFlatpakUnsupported
              : message}
          </div>
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        <ToggleField
          label={strings.rustDeskPointerFix}
          description={strings.rustDeskPointerFixDescription}
          checked={flatpakUnsupported
            ? false
            : status?.rustDeskPointerFixEnabled ?? false}
          disabled={busy || !status?.available || flatpakUnsupported}
          onChange={(enabled) =>
            void update(() => api.setRustDeskPointerFixEnabled(enabled))}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label={strings.rustDeskFocusOnInput}
          description={strings.rustDeskFocusOnInputDescription}
          checked={flatpakUnsupported
            ? false
            : status?.rustDeskFocusOnInputEnabled ?? false}
          disabled={busy || !status?.available || flatpakUnsupported}
          onChange={(enabled) =>
            void update(
              () => api.setRustDeskFocusOnInputEnabled(enabled),
            )}
        />
      </PanelSectionRow>
      <PanelSectionRow>
        <ToggleField
          label={strings.rustDeskScrollInertia}
          description={strings.rustDeskScrollInertiaDescription}
          checked={flatpakUnsupported
            ? false
            : status?.rustDeskScrollInertiaEnabled ?? false}
          disabled={
            busy
            || !status?.available
            || flatpakUnsupported
            || !status.rustDeskPointerFixEnabled
          }
          onChange={(enabled) =>
            void update(
              () => api.setRustDeskScrollInertiaEnabled(enabled),
            )}
        />
      </PanelSectionRow>
    </PanelSection>
  );
};
