export interface TrackpadMetricsSample {
  timestampMs: number;
  sequence: number;
  streamEpoch: number;
  leftTouched: boolean;
  leftPressed: boolean;
  leftPressure: number;
  leftX: number;
  leftY: number;
  rightTouched: boolean;
  rightPressed: boolean;
  rightPressure: number;
  rightX: number;
  rightY: number;
  buttons: number;
}

export interface TrackpadMetricsCapture {
  id: string;
  createdAtMs: number;
  reason: string;
  automatic: boolean;
  sampleCount: number;
  durationMs: number;
  leftPeakPressure: number;
  rightPeakPressure: number;
}

export interface TrackpadMetricsStatus {
  available: boolean;
  running: boolean;
  devicePath: string;
  sampleCount: number;
  retainedSeconds: number;
  capacitySeconds: number;
  sampleRateHz: number;
  latest?: TrackpadMetricsSample | null;
  captures: TrackpadMetricsCapture[];
  error?: string;
}

export interface DeveloperSettingsStatus {
  developerMode: boolean;
  trackpadMetricsEnabled: boolean;
  metrics: TrackpadMetricsStatus;
  error?: string;
}

export interface TrackpadMetricsWindow {
  captureId: string;
  sampleCount: number;
  samples: TrackpadMetricsSample[];
  summary?: TrackpadMetricsCapture;
  error?: string;
}

export interface DeveloperApi {
  getStatus(): Promise<DeveloperSettingsStatus>;
  setDeveloperMode(enabled: boolean): Promise<DeveloperSettingsStatus>;
  setTrackpadMetricsEnabled(
    enabled: boolean,
  ): Promise<DeveloperSettingsStatus>;
  getTrackpadMetricsWindow(
    captureId: string,
    maxSamples: number,
  ): Promise<TrackpadMetricsWindow>;
  captureTrackpadMetrics(): Promise<DeveloperSettingsStatus>;
  clearTrackpadMetricsBuffer(): Promise<DeveloperSettingsStatus>;
  deleteTrackpadMetricsCapture(
    captureId: string,
  ): Promise<DeveloperSettingsStatus>;
}
