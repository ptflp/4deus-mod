import {
  ConfirmModal,
  DialogButton,
  DropdownItem,
  PanelSection,
  PanelSectionRow,
  showModal,
  ToggleField,
} from "@decky/ui";
import {
  useEffect,
  useMemo,
  useState,
} from "react";

import { useStrings, type Strings } from "../../core/localization";
import { TrackpadMetricsGraph } from "./TrackpadMetricsGraph";
import type {
  DeveloperApi,
  DeveloperSettingsStatus,
  TrackpadMetricsCapture,
  TrackpadMetricsSample,
  TrackpadMetricsWindow,
} from "./types";

const LIVE_BUFFER_ID = "";
const WINDOW_SAMPLE_LIMIT = 800;
const POLL_INTERVAL_MS = 1_000;

interface TrackpadMetricsPanelProps {
  api: DeveloperApi;
}

interface ClearBufferConfirmationProps {
  closeModal(): void;
  confirm(): void;
  strings: Strings;
}

interface MetricsToggleConfirmationProps {
  closeModal(): void;
  confirm(): void;
  strings: Strings;
}

interface PadStatusProps {
  label: string;
  pressure: number;
  touched: boolean;
  pressed: boolean;
  x: number;
  y: number;
  color: string;
  strings: Strings;
}

const errorText = (error: unknown): string =>
  error instanceof Error ? error.message : String(error);

const ClearBufferConfirmation = ({
  closeModal,
  confirm,
  strings,
}: ClearBufferConfirmationProps) => (
  <ConfirmModal
    bDestructiveWarning
    bDisableBackgroundDismiss
    closeModal={closeModal}
    onCancel={closeModal}
    onOK={confirm}
    strCancelButtonText={strings.trackpadMetricsClearCancel}
    strDescription={strings.trackpadMetricsClearConfirmation}
    strOKButtonText={strings.trackpadMetricsClearBuffer}
    strTitle={strings.trackpadMetricsClearBuffer}
  />
);

const showClearBufferConfirmation = (
  strings: Strings,
  onConfirm: () => void,
  parent?: EventTarget,
): void => {
  let modal: ReturnType<typeof showModal> | undefined;
  let closed = false;
  const close = (): void => {
    if (closed)
      return;
    closed = true;
    modal?.Close();
  };
  const confirm = (): void => {
    close();
    onConfirm();
  };
  modal = showModal(
    <ClearBufferConfirmation
      closeModal={close}
      confirm={confirm}
      strings={strings}
    />,
    parent,
    {
      bHideMainWindowForPopouts: false,
      bNeverPopOut: true,
      strTitle: "4deus Mod",
    },
  );
};

const MetricsToggleConfirmation = ({
  closeModal,
  confirm,
  strings,
}: MetricsToggleConfirmationProps) => {
  const [unlockAt] = useState(() => Date.now() + 5_000);
  const [remaining, setRemaining] = useState(5);

  useEffect(() => {
    const update = (): void => {
      setRemaining(Math.max(0, Math.ceil(
        (unlockAt - Date.now()) / 1_000,
      )));
    };
    update();
    const interval = window.setInterval(update, 200);
    return () => window.clearInterval(interval);
  }, [unlockAt]);

  const guardedConfirm = (): void => {
    if (Date.now() < unlockAt)
      return;
    confirm();
  };

  return (
    <ConfirmModal
      bDisableBackgroundDismiss
      bOKDisabled={remaining > 0}
      closeModal={closeModal}
      onCancel={closeModal}
      onOK={guardedConfirm}
      strCancelButtonText={strings.trackpadMetricsClearCancel}
      strDescription={strings.trackpadMetricsToggleConfirmation}
      strOKButtonText={remaining > 0
        ? `${strings.trackpadMetricsConfirm} (${remaining})`
        : strings.trackpadMetricsConfirm}
      strTitle={strings.trackpadMetrics}
    />
  );
};

const showMetricsToggleConfirmation = (
  strings: Strings,
  onConfirm: () => void,
  parent?: EventTarget,
): void => {
  let modal: ReturnType<typeof showModal> | undefined;
  let closed = false;
  const close = (): void => {
    if (closed)
      return;
    closed = true;
    modal?.Close();
  };
  const confirm = (): void => {
    close();
    onConfirm();
  };
  modal = showModal(
    <MetricsToggleConfirmation
      closeModal={close}
      confirm={confirm}
      strings={strings}
    />,
    parent,
    {
      bHideMainWindowForPopouts: false,
      bNeverPopOut: true,
      strTitle: "4deus Mod",
    },
  );
};

const formatDuration = (seconds: number): string => {
  if (seconds < 60)
    return `${seconds.toFixed(1)} s`;
  return `${(seconds / 60).toFixed(1)} min`;
};

const captureLabel = (
  capture: TrackpadMetricsCapture,
  strings: Strings,
): string => {
  const kind = capture.reason === "rolling-journal"
    ? strings.trackpadMetricsJournal
    : (
      capture.automatic
        ? strings.automatic
        : strings.trackpadMetricsManual
    );
  return `${new Date(capture.createdAtMs).toLocaleString()} · ${kind}`;
};

const PadStatus = ({
  label,
  pressure,
  touched,
  pressed,
  x,
  y,
  color,
  strings,
}: PadStatusProps) => (
  <div
    style={{
      background: "rgba(0, 0, 0, 0.22)",
      borderLeft: `4px solid ${color}`,
      borderRadius: "6px",
      boxSizing: "border-box",
      minWidth: 0,
      padding: "14px 16px",
    }}
  >
    <div style={{ fontSize: "16px", fontWeight: 600 }}>{label}</div>
    <div style={{ fontSize: "28px", fontWeight: 700, marginTop: "5px" }}>
      {pressure}
    </div>
    <div style={{ color: "rgba(255,255,255,0.66)", fontSize: "12px" }}>
      {strings.trackpadMetricsPressure} · X {x} · Y {y}
    </div>
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "6px",
        marginTop: "10px",
      }}
    >
      <span>{`${touched ? "●" : "○"} ${
        strings.trackpadMetricsTouched
      }`}</span>
      <span>{`${pressed ? "●" : "○"} ${
        strings.trackpadMetricsPressed
      }`}</span>
    </div>
  </div>
);

const LatestTrackpads = ({
  sample,
  strings,
}: {
  sample?: TrackpadMetricsSample | null;
  strings: Strings;
}) => {
  if (!sample)
    return null;
  return (
    <div
      style={{
        display: "grid",
        gap: "12px",
        gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
        width: "100%",
      }}
    >
      <PadStatus
        label={strings.trackpadMetricsLeft}
        pressure={sample.leftPressure}
        touched={sample.leftTouched}
        pressed={sample.leftPressed}
        x={sample.leftX}
        y={sample.leftY}
        color="#66c0f4"
        strings={strings}
      />
      <PadStatus
        label={strings.trackpadMetricsRight}
        pressure={sample.rightPressure}
        touched={sample.rightTouched}
        pressed={sample.rightPressed}
        x={sample.rightX}
        y={sample.rightY}
        color="#d799ff"
        strings={strings}
      />
    </div>
  );
};

export const TrackpadMetricsPanel = ({
  api,
}: TrackpadMetricsPanelProps) => {
  const strings = useStrings();
  const [status, setStatus] = useState<DeveloperSettingsStatus>();
  const [metricsWindow, setMetricsWindow] =
    useState<TrackpadMetricsWindow>();
  const [selectedCaptureId, setSelectedCaptureId] = useState(
    LIVE_BUFFER_ID,
  );
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    const refresh = async (): Promise<void> => {
      try {
        const [nextStatus, nextWindow] = await Promise.all([
          api.getStatus(),
          api.getTrackpadMetricsWindow(
            selectedCaptureId,
            WINDOW_SAMPLE_LIMIT,
          ),
        ]);
        if (!active)
          return;
        setStatus(nextStatus);
        setMetricsWindow(nextWindow);
        if (nextStatus.error || nextWindow.error)
          setMessage(nextStatus.error ?? nextWindow.error ?? "");
      } catch (error) {
        if (active)
          setMessage(errorText(error));
      }
    };

    void refresh();
    const interval = selectedCaptureId === LIVE_BUFFER_ID
      ? window.setInterval(() => void refresh(), POLL_INTERVAL_MS)
      : undefined;
    return () => {
      active = false;
      if (interval !== undefined)
        window.clearInterval(interval);
    };
  }, [api, selectedCaptureId]);

  const sourceOptions = useMemo(() => [
    {
      data: LIVE_BUFFER_ID,
      label: strings.trackpadMetricsLive,
    },
    ...(status?.metrics.captures ?? []).map((capture) => ({
      data: capture.id,
      label: captureLabel(capture, strings),
    })),
  ], [status?.metrics.captures, strings]);

  const selectedCapture = useMemo(
    () => status?.metrics.captures.find(
      (capture) => capture.id === selectedCaptureId,
    ),
    [selectedCaptureId, status?.metrics.captures],
  );

  const runStatusAction = async (
    action: () => Promise<DeveloperSettingsStatus>,
    onSuccess?: (nextStatus: DeveloperSettingsStatus) => void,
  ): Promise<void> => {
    setBusy(true);
    setMessage("");
    try {
      const nextStatus = await action();
      setStatus(nextStatus);
      setMessage(nextStatus.error ?? "");
      if (!nextStatus.error)
        onSuccess?.(nextStatus);
    } catch (error) {
      setMessage(errorText(error));
    } finally {
      setBusy(false);
    }
  };

  const saveCapture = (): void => {
    void runStatusAction(api.captureTrackpadMetrics, (nextStatus) => {
      const newestCapture = nextStatus.metrics.captures[0];
      if (newestCapture)
        setSelectedCaptureId(newestCapture.id);
      setMessage(strings.trackpadMetricsCaptureSaved);
    });
  };

  const deleteCapture = (): void => {
    if (!selectedCaptureId)
      return;
    const captureId = selectedCaptureId;
    void runStatusAction(
      () => api.deleteTrackpadMetricsCapture(captureId),
      () => setSelectedCaptureId(LIVE_BUFFER_ID),
    );
  };

  const metrics = status?.metrics;
  const visibleSamples = metricsWindow?.samples ?? [];
  const latest = selectedCaptureId
    ? visibleSamples[visibleSamples.length - 1]
    : metrics?.latest;

  return (
    <>
      <PanelSection title={strings.trackpadMetrics}>
        <PanelSectionRow>
          <div>{strings.trackpadMetricsDescription}</div>
        </PanelSectionRow>
        <PanelSectionRow>
          <div style={{ color: "rgba(255,255,255,0.66)" }}>
            {strings.trackpadMetricsPrivacy}
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label={strings.trackpadMetrics}
            description={status?.developerMode
              ? strings.trackpadMetricsCaptureDescription
              : strings.trackpadMetricsEnableDeveloperFirst}
            checked={status?.trackpadMetricsEnabled ?? false}
            disabled={busy || !status?.developerMode || !metrics?.available}
            onChange={(enabled) =>
              showMetricsToggleConfirmation(
                strings,
                () => void runStatusAction(
                  () => api.setTrackpadMetricsEnabled(enabled),
                ),
              )}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <div>
            {`${metrics?.running
              ? strings.trackpadMetricsRunning
              : strings.trackpadMetricsStopped
            } · ${strings.trackpadMetricsSamples}: ${
              metrics?.sampleCount ?? 0
            } · ${strings.trackpadMetricsRetention}: ${
              formatDuration(metrics?.retainedSeconds ?? 0)
            } / ${formatDuration(metrics?.capacitySeconds ?? 0)}`}
          </div>
        </PanelSectionRow>
        {metrics?.devicePath && (
          <PanelSectionRow>
            <div
              style={{
                color: "rgba(255,255,255,0.66)",
                fontFamily: "monospace",
              }}
            >
              {`${strings.trackpadMetricsDevice}: ${metrics.devicePath}`}
            </div>
          </PanelSectionRow>
        )}
        {!status && (
          <PanelSectionRow>
            <div>{strings.systemToolsLoading}</div>
          </PanelSectionRow>
        )}
        {(message || metrics?.error) && (
          <PanelSectionRow>
            <div>{message || metrics?.error}</div>
          </PanelSectionRow>
        )}
      </PanelSection>

      <PanelSection title={strings.trackpadMetricsLiveBuffer}>
        <PanelSectionRow>
          <DropdownItem
            label={strings.trackpadMetricsCaptures}
            menuLabel={strings.trackpadMetricsCaptures}
            rgOptions={sourceOptions}
            selectedOption={selectedCaptureId}
            disabled={busy}
            onChange={({ data }) => setSelectedCaptureId(data.toString())}
          />
        </PanelSectionRow>
        {selectedCapture && (
          <PanelSectionRow>
            <div>
              {`${captureLabel(selectedCapture, strings)} · ${
                strings.trackpadMetricsSamples
              }: ${selectedCapture.sampleCount} · ${
                strings.trackpadMetricsPressure
              }: ${selectedCapture.leftPeakPressure} / ${
                selectedCapture.rightPeakPressure
              }`}
            </div>
          </PanelSectionRow>
        )}
        <PanelSectionRow>
          <TrackpadMetricsGraph
            samples={visibleSamples}
            strings={strings}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <LatestTrackpads sample={latest} strings={strings} />
        </PanelSectionRow>
        <PanelSectionRow>
          <DialogButton
            disabled={busy || !metrics?.sampleCount}
            onClick={saveCapture}
            style={{ width: "100%" }}
          >
            {strings.trackpadMetricsSaveCapture}
          </DialogButton>
        </PanelSectionRow>
        <PanelSectionRow>
          <DialogButton
            disabled={busy || !metrics?.sampleCount}
            onClick={(event) => showClearBufferConfirmation(
              strings,
              () => void runStatusAction(
                api.clearTrackpadMetricsBuffer,
              ),
              event.currentTarget ?? undefined,
            )}
            style={{ width: "100%" }}
          >
            {strings.trackpadMetricsClearBuffer}
          </DialogButton>
        </PanelSectionRow>
        {selectedCapture
          && selectedCapture.reason !== "rolling-journal"
          && (
          <PanelSectionRow>
            <DialogButton
              disabled={busy}
              onClick={deleteCapture}
              style={{ width: "100%" }}
            >
              {strings.trackpadMetricsDeleteCapture}
            </DialogButton>
          </PanelSectionRow>
          )}
      </PanelSection>
    </>
  );
};
