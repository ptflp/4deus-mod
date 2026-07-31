import type { SteamArtworkPayload } from "../../core/steamArtwork";

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
  aliases?: string[];
  artworkId?: string;
  error?: string;
  icon: string;
  id: string;
  launcherPath: string;
  name: string;
  startDirectory: string;
}

export interface AppBridgeArtworkResult {
  artworkId?: string;
  error?: string;
  gridDirectory?: string;
  installed: number;
  liveArtwork?: SteamArtworkPayload;
  liveLogoPosition?: string;
  preserved: number;
}

export interface AppBridgeStatus {
  chromeInstalled: boolean;
  chromeProfileInstalled: boolean;
  launcherInstalled: boolean;
  launcherPath: string;
  parsecInstalled: boolean;
  parsecProfileInstalled: boolean;
  rustdeskInstalled: boolean;
  rustdeskProfileInstalled: boolean;
  terminalInstalled: boolean;
  terminalProfileInstalled: boolean;
}

export interface AppBridgeApi {
  getStatus(): Promise<AppBridgeStatus>;
  installArtwork(
    artworkId: string,
    appId: number,
  ): Promise<AppBridgeArtworkResult>;
  listApplications(): Promise<AppBridgeApplication[]>;
  prepareChrome(): Promise<PreparedAppBridgeProfile>;
  prepareParsec(): Promise<PreparedAppBridgeProfile>;
  prepareRustDesk(): Promise<PreparedAppBridgeProfile>;
  prepareTerminal(): Promise<PreparedAppBridgeProfile>;
  saveProfile(
    profile: AppBridgeProfileDraft,
  ): Promise<PreparedAppBridgeProfile>;
}
