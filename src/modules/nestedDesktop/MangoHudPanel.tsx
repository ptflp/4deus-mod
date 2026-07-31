import {
  DialogButton,
  PanelSection,
  PanelSectionRow,
} from "@decky/ui";
import { useEffect, useState } from "react";

import { useStrings, type Strings } from "../../core/localization";
import type {
  MangoHudApi,
  MangoHudFixStatus,
} from "./types";

interface MangoHudPanelProps {
  api: MangoHudApi;
}

const statusLabel = (
  status: MangoHudFixStatus | undefined,
  strings: Strings,
): string => {
  if (!status)
    return strings.systemToolsLoading;
  if (!status.available)
    return strings.mangoHudFixUnavailable;
  if (status.current)
    return strings.mangoHudFixInstalled;
  if (status.installed)
    return strings.mangoHudFixNeedsRepair;
  return strings.mangoHudFixNotInstalled;
};

export const MangoHudPanel = ({ api }: MangoHudPanelProps) => {
  const strings = useStrings();
  const [status, setStatus] = useState<MangoHudFixStatus>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.getMangoHudFixStatus()
      .then(setStatus)
      .catch((error) => setMessage(
        error instanceof Error ? error.message : String(error),
      ));
  }, []);

  const runAction = async (
    action: () => Promise<MangoHudFixStatus>,
    successMessage: string,
  ): Promise<void> => {
    setBusy(true);
    setMessage("");
    try {
      const nextStatus = await action();
      setStatus(nextStatus);
      setMessage(nextStatus.error ?? successMessage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <PanelSection title={strings.mangoHudFix}>
      <PanelSectionRow>
        <div>{strings.mangoHudFixDescription}</div>
      </PanelSectionRow>
      <PanelSectionRow>
        <div>{`${strings.systemToolsStatus}: ${
          statusLabel(status, strings)
        }`}</div>
      </PanelSectionRow>
      <PanelSectionRow>
        <DialogButton
          disabled={busy || !status?.available}
          onClick={() => void runAction(
            api.installMangoHudFix,
            strings.mangoHudFixApplied,
          )}
          style={{ width: "100%" }}
        >
          {strings.installOrRepairMangoHudFix}
        </DialogButton>
      </PanelSectionRow>
      {status?.installed && (
        <PanelSectionRow>
          <DialogButton
            disabled={busy}
            onClick={() => void runAction(
              api.removeMangoHudFix,
              strings.mangoHudFixRemoved,
            )}
            style={{ width: "100%" }}
          >
            {strings.removeMangoHudFix}
          </DialogButton>
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
