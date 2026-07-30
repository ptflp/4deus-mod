import {
  DialogButton,
  PanelSection,
  PanelSectionRow,
  ToggleField,
} from "@decky/ui";
import { useEffect, useState } from "react";

import { useStrings, type Strings } from "../../core/localization";
import {
  ensureSteamOsShortcut,
  findSteamOsShortcut,
} from "../appBridge/steamShortcuts";
import type {
  MangoHudFixStatus,
  NestedDesktopMouseStatus,
  SteamOsApplicationStatus,
  SystemToolsApi,
} from "./types";

interface SystemToolsPanelProps {
  api: SystemToolsApi;
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

const steamOsStatusLabel = (
  status: SteamOsApplicationStatus | undefined,
  shortcutAppId: number | undefined,
  strings: Strings,
): string => {
  if (!status)
    return strings.systemToolsLoading;
  if (!status.available)
    return strings.mangoHudFixUnavailable;
  if (!shortcutAppId)
    return strings.mangoHudFixNotInstalled;
  return status.current
    ? strings.mangoHudFixInstalled
    : strings.mangoHudFixNeedsRepair;
};

export const SystemToolsPanel = ({ api }: SystemToolsPanelProps) => {
  const strings = useStrings();
  const [status, setStatus] = useState<MangoHudFixStatus>();
  const [steamOsStatus, setSteamOsStatus] =
    useState<SteamOsApplicationStatus>();
  const [nestedDesktopMouseStatus, setNestedDesktopMouseStatus] =
    useState<NestedDesktopMouseStatus>();
  const [steamOsShortcutAppId, setSteamOsShortcutAppId] = useState<
    number | undefined
  >(() => findSteamOsShortcut()?.appid);
  const [busy, setBusy] = useState(false);
  const [mangoHudMessage, setMangoHudMessage] = useState("");
  const [steamOsMessage, setSteamOsMessage] = useState("");

  const loadStatus = async (): Promise<void> => {
    try {
      const [
        nextMangoHudStatus,
        nextSteamOsStatus,
        nextNestedDesktopMouseStatus,
      ] = await Promise.all([
        api.getMangoHudFixStatus(),
        api.getSteamOsApplicationStatus(),
        api.getNestedDesktopMouseStatus(),
      ]);
      setStatus(nextMangoHudStatus);
      setSteamOsStatus(nextSteamOsStatus);
      setNestedDesktopMouseStatus(nextNestedDesktopMouseStatus);
      setSteamOsShortcutAppId(findSteamOsShortcut()?.appid);
    } catch (error) {
      setMangoHudMessage(
        error instanceof Error ? error.message : String(error),
      );
    }
  };

  useEffect(() => {
    void loadStatus();
  }, []);

  const runAction = async (
    action: () => Promise<MangoHudFixStatus>,
    successMessage: string,
  ): Promise<void> => {
    setBusy(true);
    setMangoHudMessage("");
    try {
      const nextStatus = await action();
      setStatus(nextStatus);
      setMangoHudMessage(nextStatus.error ?? successMessage);
    } catch (error) {
      setMangoHudMessage(
        error instanceof Error ? error.message : String(error),
      );
    } finally {
      setBusy(false);
    }
  };

  const installSteamOsApplication = async (): Promise<void> => {
    setBusy(true);
    setSteamOsMessage("");
    try {
      const profile = await api.prepareSteamOsApplication();
      if (profile.error)
        throw new Error(profile.error);
      const appId = await ensureSteamOsShortcut(profile);
      const artwork = await api.installSteamOsApplicationArtwork(appId);
      if (artwork.error)
        throw new Error(artwork.error);
      setSteamOsStatus(profile);
      setSteamOsShortcutAppId(appId);
      setSteamOsMessage(strings.steamOsApplicationReady);
    } catch (error) {
      setSteamOsMessage(
        error instanceof Error ? error.message : String(error),
      );
    } finally {
      setBusy(false);
    }
  };

  const setNestedDesktopMouseEnabled = async (
    enabled: boolean,
  ): Promise<void> => {
    setBusy(true);
    setSteamOsMessage("");
    try {
      const nextStatus = await api.setNestedDesktopMouseEnabled(enabled);
      setNestedDesktopMouseStatus(nextStatus);
      if (nextStatus.error)
        setSteamOsMessage(nextStatus.error);
    } catch (error) {
      setSteamOsMessage(
        error instanceof Error ? error.message : String(error),
      );
    } finally {
      setBusy(false);
    }
  };

  const setNestedDesktopMouseInertiaEnabled = async (
    enabled: boolean,
  ): Promise<void> => {
    setBusy(true);
    setSteamOsMessage("");
    try {
      const nextStatus =
        await api.setNestedDesktopMouseInertiaEnabled(enabled);
      setNestedDesktopMouseStatus(nextStatus);
      if (nextStatus.error)
        setSteamOsMessage(nextStatus.error);
    } catch (error) {
      setSteamOsMessage(
        error instanceof Error ? error.message : String(error),
      );
    } finally {
      setBusy(false);
    }
  };

  const setRustDeskPointerFixEnabled = async (
    enabled: boolean,
  ): Promise<void> => {
    setBusy(true);
    setSteamOsMessage("");
    try {
      const nextStatus =
        await api.setRustDeskPointerFixEnabled(enabled);
      setNestedDesktopMouseStatus(nextStatus);
      if (nextStatus.error)
        setSteamOsMessage(nextStatus.error);
    } catch (error) {
      setSteamOsMessage(
        error instanceof Error ? error.message : String(error),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PanelSection title={strings.steamOsApplication}>
        <PanelSectionRow>
          <div>{strings.steamOsApplicationDescription}</div>
        </PanelSectionRow>
        <PanelSectionRow>
          <div>{`${strings.systemToolsStatus}: ${
            steamOsStatusLabel(
              steamOsStatus,
              steamOsShortcutAppId,
              strings,
            )
          }`}</div>
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label={strings.nestedDesktopMouseBridge}
            description={strings.nestedDesktopMouseBridgeDescription}
            checked={nestedDesktopMouseStatus?.enabled ?? false}
            disabled={busy || !nestedDesktopMouseStatus?.available}
            onChange={(enabled) => void setNestedDesktopMouseEnabled(enabled)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label={strings.nestedDesktopTrackpadInertia}
            description={strings.nestedDesktopTrackpadInertiaDescription}
            checked={nestedDesktopMouseStatus?.inertiaEnabled ?? true}
            disabled={
              busy
              || !nestedDesktopMouseStatus?.available
              || !nestedDesktopMouseStatus.enabled
            }
            onChange={(enabled) =>
              void setNestedDesktopMouseInertiaEnabled(enabled)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label={strings.rustDeskPointerFix}
            description={strings.rustDeskPointerFixDescription}
            checked={
              nestedDesktopMouseStatus?.rustDeskPointerFixEnabled ?? true
            }
            disabled={
              busy
              || !nestedDesktopMouseStatus?.available
            }
            onChange={(enabled) =>
              void setRustDeskPointerFixEnabled(enabled)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <DialogButton
            disabled={busy || !steamOsStatus?.available}
            onClick={() => void installSteamOsApplication()}
            style={{ width: "100%" }}
          >
            {strings.addOrRepairSteamOsApplication}
          </DialogButton>
        </PanelSectionRow>
        {steamOsMessage && (
          <PanelSectionRow>
            <div>{steamOsMessage}</div>
          </PanelSectionRow>
        )}
      </PanelSection>

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
        {mangoHudMessage && (
          <PanelSectionRow>
            <div>{mangoHudMessage}</div>
          </PanelSectionRow>
        )}
      </PanelSection>
    </>
  );
};
