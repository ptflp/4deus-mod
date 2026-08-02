import type { SteamArtworkPayload } from "../../core/steamArtwork";
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
}

export interface MangoHudApi {
  getMangoHudFixStatus(): Promise<MangoHudFixStatus>;
  installMangoHudFix(): Promise<MangoHudFixStatus>;
  removeMangoHudFix(): Promise<MangoHudFixStatus>;
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
  liveArtwork?: SteamArtworkPayload;
  liveLogoPosition?: string;
  preserved: number;
}

export interface TouchscreenInertiaConfig {
  durationMs: number;
  minDistance: number;
  startSpeed: number;
}

export interface NestedDesktopMouseStatus {
  available: boolean;
  bindings: NestedDesktopBindings;
  bindingsEnabled: boolean;
  clipboardEnabled: boolean;
  clipboardFilesEnabled: boolean;
  enabled: boolean;
  error?: string;
  errorCode?: string;
  gamescopePointerRelayEnabled: boolean;
  inertiaEnabled: boolean;
  moduleEnabled: boolean;
  rustDeskFocusOnInputEnabled: boolean;
  rustDeskFlatpakInstalled: boolean;
  rustDeskPointerFixEnabled: boolean;
  rustDeskScrollInertiaEnabled: boolean;
  running: boolean;
  suspended: boolean;
  touchAvailable: boolean;
  touchEnabled: boolean;
  touchInertiaConfig: TouchscreenInertiaConfig;
  touchInertiaEnabled: boolean;
}

export interface NestedDesktopApi {
  getSteamOsApplicationStatus(): Promise<SteamOsApplicationStatus>;
  prepareSteamOsApplication(): Promise<PreparedSteamOsApplication>;
  installSteamOsApplicationArtwork(
    appId: number,
  ): Promise<SteamOsArtworkResult>;
  getNestedDesktopMouseStatus(): Promise<NestedDesktopMouseStatus>;
  setNestedDesktopModuleEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
  setNestedDesktopMouseEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
  setNestedDesktopGamescopePointerRelayEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
  setNestedDesktopClipboardEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
  setNestedDesktopClipboardFilesEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
  setNestedDesktopMouseInertiaEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
  setNestedDesktopTouchEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
  setNestedDesktopTouchInertiaEnabled(
    enabled: boolean,
  ): Promise<NestedDesktopMouseStatus>;
  setNestedDesktopTouchInertiaConfig(
    durationMs: number,
    startSpeed: number,
    minDistance: number,
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
}
