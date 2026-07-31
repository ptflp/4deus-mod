import {
  DialogButton,
  PanelSection,
  PanelSectionRow,
} from "@decky/ui";
import { useEffect, useState } from "react";

import { useStrings, type Strings } from "../../core/localization";
import type { SettingsStore } from "../../core/settings";
import {
  installSteamArtworkWithLiveRefresh,
} from "../../core/steamArtwork";
import {
  ensureSteamOsShortcut,
  findSteamOsShortcut,
} from "../appBridge/steamShortcuts";
import {
  NestedDesktopRuntimePanel,
} from "./NestedDesktopRuntimePanel";
import type {
  NestedDesktopApi,
  SteamOsApplicationStatus,
} from "./types";

interface NestedDesktopPanelProps {
  api: NestedDesktopApi;
  settings: SettingsStore;
}

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

export const NestedDesktopPanel = ({
  api,
  settings,
}: NestedDesktopPanelProps) => {
  const strings = useStrings();
  const [steamOsStatus, setSteamOsStatus] =
    useState<SteamOsApplicationStatus>();
  const [shortcutAppId, setShortcutAppId] = useState<
    number | undefined
  >(() => findSteamOsShortcut()?.appid);
  const [busy, setBusy] = useState(false);
  const [steamOsMessage, setSteamOsMessage] = useState("");

  useEffect(() => {
    api.getSteamOsApplicationStatus()
      .then((nextSteamOsStatus) => {
        setSteamOsStatus(nextSteamOsStatus);
        setShortcutAppId(findSteamOsShortcut()?.appid);
      })
      .catch((error) => setSteamOsMessage(
        error instanceof Error ? error.message : String(error),
      ));
  }, []);

  const installSteamOsApplication = async (): Promise<void> => {
    setBusy(true);
    setSteamOsMessage("");
    try {
      const profile = await api.prepareSteamOsApplication();
      if (profile.error)
        throw new Error(profile.error);
      const appId = await ensureSteamOsShortcut(profile);
      await installSteamArtworkWithLiveRefresh(
        appId,
        () => api.installSteamOsApplicationArtwork(appId),
      );
      setSteamOsStatus(profile);
      setShortcutAppId(appId);
      setSteamOsMessage(strings.steamOsApplicationReady);
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
            steamOsStatusLabel(steamOsStatus, shortcutAppId, strings)
          }`}</div>
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

      <NestedDesktopRuntimePanel api={api} settings={settings} />
    </>
  );
};
