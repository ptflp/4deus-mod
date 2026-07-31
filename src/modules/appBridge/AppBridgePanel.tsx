import {
  DialogButton,
  DropdownItem,
  PanelSection,
  PanelSectionRow,
  TextField,
  ToggleField,
} from "@decky/ui";
import { useEffect, useMemo, useState } from "react";

import { useStrings } from "../../core/localization";
import type { SettingsStore } from "../../core/settings";
import { AdvancedSettings } from "../../ui/AdvancedSettings";
import type {
  AppBridgeApi,
  AppBridgeApplication,
  AppBridgeProfileDraft,
} from "./types";
import { useAppBridgeInstaller } from "./useAppBridgeInstaller";

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

const errorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

export const AppBridgePanel = ({
  api,
  settings,
}: AppBridgePanelProps) => {
  const strings = useStrings();
  const installer = useAppBridgeInstaller(api, settings, strings);
  const [applications, setApplications] = useState<AppBridgeApplication[]>([]);
  const [selectedApplication, setSelectedApplication] = useState("");
  const [profile, setProfile] = useState(EMPTY_PROFILE);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");

  const loadApplications = async (): Promise<void> => {
    setLoading(true);
    setLoadError("");
    try {
      setApplications(await api.listApplications());
    } catch (error) {
      setLoadError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadApplications();
  }, []);

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

  const busy = loading || installer.busy;
  const canInstall = Boolean(profile.name && profile.executable);
  const applicationOptions = useMemo(
    () => applications.map((application) => ({
      data: application.id,
      label: `${application.name} · ${application.kind}`,
    })),
    [applications],
  );

  return (
    <>
      <PanelSection title={strings.appBridgeApplications}>
        <PanelSectionRow>
          <DropdownItem
            disabled={busy || applications.length === 0}
            label={strings.appBridgeSelectApplication}
            menuLabel={strings.appBridgeSelectApplication}
            rgOptions={applicationOptions}
            selectedOption={selectedApplication}
            strDefaultLabel={strings.appBridgeSelectApplication}
            onChange={({ data }) => chooseApplication(data.toString())}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <DialogButton
            disabled={busy}
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
      </PanelSection>

      <AdvancedSettings
        label={strings.advancedSettings}
        description={strings.advancedSettingsDescription}
        moduleId="appBridge"
        settings={settings}
      >
        <PanelSection>
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
        </PanelSection>
      </AdvancedSettings>

      <PanelSection>
        <PanelSectionRow>
          <DialogButton
            disabled={busy || !canInstall}
            onClick={() => void installer.install(
              () => api.saveProfile(profile),
            )}
            style={{ width: "100%" }}
          >
            {strings.addOrFixApplication}
          </DialogButton>
        </PanelSectionRow>
        {(loadError || installer.message) && (
          <PanelSectionRow>
            <div>{loadError || installer.message}</div>
          </PanelSectionRow>
        )}
      </PanelSection>
    </>
  );
};
