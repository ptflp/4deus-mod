export interface ControllerStatus {
  armed: boolean;
  autoRecoveryEnabled: boolean;
  available: boolean;
  enabled: boolean;
  error?: string;
  lastAttemptAtMs: number;
  lastSuccessAtMs: number;
  moduleEnabled: boolean;
  monitoring: boolean;
  pending: boolean;
  successCount: number;
}

export interface ControllerApi {
  getControllerStatus(): Promise<ControllerStatus>;
  setControllerModuleEnabled(
    enabled: boolean,
  ): Promise<ControllerStatus>;
  setTrackpadAutoRecoveryEnabled(
    enabled: boolean,
  ): Promise<ControllerStatus>;
}
