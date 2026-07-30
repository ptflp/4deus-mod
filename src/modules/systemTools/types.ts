import type {
  NestedDesktopBindingAction,
  NestedDesktopBindings,
  NestedDesktopBindingSource,
} from "./nestedDesktopBindings";

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
  bindings: NestedDesktopBindings;
  bindingsEnabled: boolean;
  enabled: boolean;
  error?: string;
  inertiaEnabled: boolean;
  rustDeskFocusOnInputEnabled: boolean;
  rustDeskPointerFixEnabled: boolean;
  rustDeskScrollInertiaEnabled: boolean;
  running: boolean;
  suspended: boolean;
}

export interface ControllerStatus {
  armed: boolean;
  autoRecoveryEnabled: boolean;
  available: boolean;
  error?: string;
  lastAttemptAtMs: number;
  lastSuccessAtMs: number;
  monitoring: boolean;
  pending: boolean;
  successCount: number;
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
  setRustDeskPointerFixEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
  setRustDeskFocusOnInputEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
  setRustDeskScrollInertiaEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
  setNestedDesktopBindingsEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
  setNestedDesktopBinding(
    source: NestedDesktopBindingSource,
    action: NestedDesktopBindingAction,
  ): Promise<NestedDesktopMouseStatus>;
  resetNestedDesktopBindings(): Promise<NestedDesktopMouseStatus>;
  getControllerStatus(): Promise<ControllerStatus>;
  setTrackpadAutoRecoveryEnabled(
    enabled: boolean,
  ): Promise<ControllerStatus>;
}
