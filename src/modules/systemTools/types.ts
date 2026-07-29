export interface MangoHudFixStatus {
  available: boolean;
  current: boolean;
  error?: string;
  installed: boolean;
  libraryPath: string;
  serviceState: string;
}

export interface SteamOsApplicationStatus {
  available: boolean;
  current: boolean;
  error?: string;
  icon: string;
  wrapperInstalled: boolean;
  wrapperPath: string;
}

export interface PreparedSteamOsApplication
  extends SteamOsApplicationStatus {
  aliases: string[];
  launchOptions: string;
  launcherPath: string;
  name: string;
  startDirectory: string;
}

export interface SteamOsArtworkResult {
  error?: string;
  gridDirectory?: string;
  installed: number;
  preserved: number;
}

export interface NestedDesktopMouseStatus {
  available: boolean;
  enabled: boolean;
  error?: string;
  inertiaEnabled: boolean;
  running: boolean;
}

export interface SystemToolsApi {
  getMangoHudFixStatus(): Promise<MangoHudFixStatus>;
  installMangoHudFix(): Promise<MangoHudFixStatus>;
  removeMangoHudFix(): Promise<MangoHudFixStatus>;
  getSteamOsApplicationStatus(): Promise<SteamOsApplicationStatus>;
  prepareSteamOsApplication(): Promise<PreparedSteamOsApplication>;
  installSteamOsApplicationArtwork(
    appId: number,
  ): Promise<SteamOsArtworkResult>;
  getNestedDesktopMouseStatus(): Promise<NestedDesktopMouseStatus>;
  setNestedDesktopMouseEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
  setNestedDesktopMouseInertiaEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
}
