import {
  DialogButton,
  DropdownItem,
  PanelSection,
  PanelSectionRow,
  TextField,
  ToggleField,
} from "@decky/ui";
import { useEffect, useState, useSyncExternalStore } from "react";

import { useStrings } from "../../core/localization";
import type { SettingsStore } from "../../core/settings";
import { ensureAppBridgeShortcut } from "./steamShortcuts";
import type {
  AppBridgeApi,
  AppBridgeApplication,
  AppBridgeProfileDraft,
  PreparedAppBridgeProfile,
} from "./types";

interface AppBridgePanelProps {
  api: AppBridgeApi;
  settings: SettingsStore;
}

const EMPTY_PROFILE: AppBridgeProfileDraft = {
  arguments: "",
  clearSteamPreload: false,
  executable: "",
  forceX11: false,
  icon: "",
  id: "",
  libraryPath: "",
  name: "",
  waitForProcess: "",
  workingDirectory: "",
};

const profileFromApplication = (
  application: AppBridgeApplication,
): AppBridgeProfileDraft => ({
  ...EMPTY_PROFILE,
  arguments: application.arguments,
  executable: application.executable,
  icon: application.icon,
  id: application.id,
  name: application.name,
  workingDirectory: application.workingDirectory,
});

export const AppBridgePanel = ({
  api,
  settings,
}: AppBridgePanelProps) => {
  const strings = useStrings();
  const snapshot = useSyncExternalStore(
    settings.subscribe,
    settings.getSnapshot,
  );
  const bridge = snapshot.appBridge;
  const [applications, setApplications] = useState<AppBridgeApplication[]>([]);
  const [selectedApplication, setSelectedApplication] = useState("");
  const [profile, setProfile] = useState(EMPTY_PROFILE);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const loadApplications = async (): Promise<void> => {
    setBusy(true);
    try {
      setApplications(await api.listApplications());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    void loadApplications();
  }, []);

  const rememberShortcut = (
    profileId: string,
    appId: number,
  ): void => settings.updateAppBridge({
    shortcutAppIds: {
      ...bridge.shortcutAppIds,
      [profileId]: appId,
    },
  });

  const installPrepared = async (
    prepared: PreparedAppBridgeProfile,
  ): Promise<void> => {
    if (prepared.error)
      throw new Error(prepared.error);
    const appId = await ensureAppBridgeShortcut(
      prepared,
      bridge.shortcutAppIds[prepared.id],
    );
    if (prepared.artworkId) {
      const artwork = await api.installArtwork(prepared.artworkId, appId);
      if (artwork.error)
        throw new Error(artwork.error);
    }
    rememberShortcut(prepared.id, appId);
    setMessage(`${strings.appBridgeReady}: ${prepared.name}`);
  };

  const installParsec = async (): Promise<void> => {
    setBusy(true);
    setMessage("");
    try {
      await installPrepared(await api.prepareParsec());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const installRustDesk = async (): Promise<void> => {
    setBusy(true);
    setMessage("");
    try {
      await installPrepared(await api.prepareRustDesk());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const installProfile = async (): Promise<void> => {
    setBusy(true);
    setMessage("");
    try {
      await installPrepared(await api.saveProfile(profile));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const chooseApplication = (applicationId: string): void => {
    setSelectedApplication(applicationId);
    const application = applications.find(
      (candidate) => candidate.id === applicationId,
    );
    if (application)
      setProfile(profileFromApplication(application));
  };

  const updateProfile = (
    patch: Partial<AppBridgeProfileDraft>,
  ): void => setProfile((current) => ({ ...current, ...patch }));

  const canInstallProfile = Boolean(profile.name && profile.executable);
  const controlsDisabled = busy;

  return (
    <>
      <PanelSection title={strings.appBridgeQuickSetup}>
        <PanelSectionRow>
          <div>{strings.appBridgeParsecDescription}</div>
        </PanelSectionRow>
        <PanelSectionRow>
          <DialogButton
            disabled={controlsDisabled}
            onClick={() => void installParsec()}
            style={{ width: "100%" }}
          >
            {strings.addOrFixParsec}
          </DialogButton>
        </PanelSectionRow>
        <PanelSectionRow>
          <div>{strings.appBridgeRustDeskDescription}</div>
        </PanelSectionRow>
        <PanelSectionRow>
          <DialogButton
            disabled={controlsDisabled}
            onClick={() => void installRustDesk()}
            style={{ width: "100%" }}
          >
            {strings.addOrFixRustDesk}
          </DialogButton>
        </PanelSectionRow>
      </PanelSection>

      <PanelSection title={strings.appBridgeApplications}>
        <PanelSectionRow>
          <DropdownItem
            disabled={controlsDisabled || applications.length === 0}
            label={strings.appBridgeSelectApplication}
            menuLabel={strings.appBridgeSelectApplication}
            rgOptions={applications.map((application) => ({
              data: application.id,
              label: `${application.name} · ${application.kind}`,
            }))}
            selectedOption={selectedApplication}
            strDefaultLabel={strings.appBridgeSelectApplication}
            onChange={({ data }) => chooseApplication(data.toString())}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <DialogButton
            disabled={controlsDisabled}
            onClick={() => void loadApplications()}
            style={{ width: "100%" }}
          >
            {strings.appBridgeLoadApplications}
          </DialogButton>
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label={strings.appBridgeName}
            value={profile.name}
            onChange={(event) => updateProfile({ name: event.target.value })}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label={strings.appBridgeExecutable}
            value={profile.executable}
            onChange={(event) => updateProfile({
              executable: event.target.value,
            })}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label={strings.appBridgeArguments}
            value={profile.arguments}
            onChange={(event) => updateProfile({
              arguments: event.target.value,
            })}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label={strings.appBridgeWorkingDirectory}
            value={profile.workingDirectory}
            onChange={(event) => updateProfile({
              workingDirectory: event.target.value,
            })}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label={strings.appBridgeTrackProcess}
            value={profile.waitForProcess}
            onChange={(event) => updateProfile({
              waitForProcess: event.target.value,
            })}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label={strings.appBridgeClearSteamRuntime}
            checked={profile.clearSteamPreload}
            disabled={busy}
            onChange={(clearSteamPreload) => updateProfile({
              clearSteamPreload,
            })}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label={strings.appBridgeForceX11}
            checked={profile.forceX11}
            disabled={busy}
            onChange={(forceX11) => updateProfile({ forceX11 })}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label={strings.appBridgeLibraryPath}
            value={profile.libraryPath}
            onChange={(event) => updateProfile({
              libraryPath: event.target.value,
            })}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <DialogButton
            disabled={controlsDisabled || !canInstallProfile}
            onClick={() => void installProfile()}
            style={{ width: "100%" }}
          >
            {strings.addOrFixApplication}
          </DialogButton>
        </PanelSectionRow>
        {message && (
          <PanelSectionRow>
            <div>{message}</div>
          </PanelSectionRow>
        )}
      </PanelSection>
    </>
  );
};
