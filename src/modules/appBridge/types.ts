export interface AppBridgeApplication {
  arguments: string;
  executable: string;
  icon: string;
  id: string;
  kind: "desktop" | "flatpak";
  name: string;
  workingDirectory: string;
}

export interface AppBridgeProfileDraft {
  arguments: string;
  clearSteamPreload: boolean;
  executable: string;
  forceX11: boolean;
  icon: string;
  id: string;
  libraryPath: string;
  name: string;
  waitForProcess: string;
  workingDirectory: string;
}

export interface PreparedAppBridgeProfile {
  error?: string;
  icon: string;
  id: string;
  launcherPath: string;
  name: string;
  startDirectory: string;
}

export interface AppBridgeStatus {
  launcherInstalled: boolean;
  launcherPath: string;
  parsecInstalled: boolean;
  parsecProfileInstalled: boolean;
  rustdeskInstalled: boolean;
  rustdeskProfileInstalled: boolean;
}

export interface AppBridgeApi {
  getStatus(): Promise<AppBridgeStatus>;
  listApplications(): Promise<AppBridgeApplication[]>;
  prepareParsec(): Promise<PreparedAppBridgeProfile>;
  prepareRustDesk(): Promise<PreparedAppBridgeProfile>;
  saveProfile(
    profile: AppBridgeProfileDraft,
  ): Promise<PreparedAppBridgeProfile>;
}
