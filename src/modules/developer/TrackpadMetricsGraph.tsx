import { useMemo } from "react";

import type { Strings } from "../../core/localization";
import type { TrackpadMetricsSample } from "./types";

const WIDTH = 760;
const HEIGHT = 250;
const LEFT = 54;
const RIGHT = 18;
const TOP = 22;
const BOTTOM = 40;
const CLICK_THRESHOLD = 2_000;

interface TrackpadMetricsGraphProps {
  samples: TrackpadMetricsSample[];
  strings: Strings;
}

const pressureCeiling = (samples: TrackpadMetricsSample[]): number => {
  const peak = samples.reduce(
    (current, sample) => Math.max(
      current,
      sample.leftPressure,
      sample.rightPressure,
    ),
    0,
  );
  return Math.max(6_000, Math.ceil(peak / 1_000) * 1_000);
};

const samplePoints = (
  samples: TrackpadMetricsSample[],
  maximum: number,
  selectPressure: (sample: TrackpadMetricsSample) => number,
): string => {
  const firstTime = samples[0]?.timestampMs ?? 0;
  const lastTime = samples[samples.length - 1]?.timestampMs ?? firstTime;
  const duration = Math.max(1, lastTime - firstTime);
  const graphWidth = WIDTH - LEFT - RIGHT;
  const graphHeight = HEIGHT - TOP - BOTTOM;

  return samples.map((sample) => {
    const x = LEFT
      + ((sample.timestampMs - firstTime) / duration) * graphWidth;
    const y = TOP
      + (1 - Math.min(maximum, selectPressure(sample)) / maximum)
        * graphHeight;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
};

const graphTimeLabel = (samples: TrackpadMetricsSample[]): string => {
  if (samples.length < 2)
    return "0 s";
  const duration = (
    samples[samples.length - 1].timestampMs - samples[0].timestampMs
  ) / 1_000;
  if (duration < 60)
    return `${duration.toFixed(1)} s`;
  return `${(duration / 60).toFixed(1)} min`;
};

export const TrackpadMetricsGraph = ({
  samples,
  strings,
}: TrackpadMetricsGraphProps) => {
  const chart = useMemo(() => {
    const maximum = pressureCeiling(samples);
    return {
      maximum,
      left: samplePoints(
        samples,
        maximum,
        (sample) => sample.leftPressure,
      ),
      right: samplePoints(
        samples,
        maximum,
        (sample) => sample.rightPressure,
      ),
      thresholdY: TOP
        + (1 - CLICK_THRESHOLD / maximum) * (HEIGHT - TOP - BOTTOM),
      timeLabel: graphTimeLabel(samples),
    };
  }, [samples]);

  if (samples.length === 0) {
    return (
      <div
        style={{
          alignItems: "center",
          background: "rgba(0, 0, 0, 0.22)",
          borderRadius: "6px",
          boxSizing: "border-box",
          display: "flex",
          justifyContent: "center",
          minHeight: "250px",
          padding: "24px",
          width: "100%",
        }}
      >
        {strings.trackpadMetricsNoData}
      </div>
    );
  }

  return (
    <div
      style={{
        background: "rgba(0, 0, 0, 0.22)",
        borderRadius: "6px",
        boxSizing: "border-box",
        overflow: "hidden",
        padding: "10px",
        width: "100%",
      }}
    >
      <svg
        aria-label={strings.trackpadMetricsPressure}
        role="img"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        style={{ display: "block", height: "250px", width: "100%" }}
      >
        <line
          x1={LEFT}
          x2={WIDTH - RIGHT}
          y1={TOP}
          y2={TOP}
          stroke="rgba(255,255,255,0.13)"
        />
        <line
          x1={LEFT}
          x2={WIDTH - RIGHT}
          y1={HEIGHT - BOTTOM}
          y2={HEIGHT - BOTTOM}
          stroke="rgba(255,255,255,0.22)"
        />
        <line
          x1={LEFT}
          x2={WIDTH - RIGHT}
          y1={chart.thresholdY}
          y2={chart.thresholdY}
          stroke="#f3a847"
          strokeDasharray="8 6"
          strokeWidth="1.5"
        />
        <text x="6" y={TOP + 5} fill="rgba(255,255,255,0.72)" fontSize="13">
          {chart.maximum}
        </text>
        <text
          x="6"
          y={chart.thresholdY + 5}
          fill="#f3a847"
          fontSize="13"
        >
          {CLICK_THRESHOLD}
        </text>
        <text
          x={LEFT}
          y={HEIGHT - 12}
          fill="rgba(255,255,255,0.65)"
          fontSize="13"
        >
          0
        </text>
        <text
          x={WIDTH - RIGHT}
          y={HEIGHT - 12}
          fill="rgba(255,255,255,0.65)"
          fontSize="13"
          textAnchor="end"
        >
          {chart.timeLabel}
        </text>
        <polyline
          fill="none"
          points={chart.left}
          stroke="#66c0f4"
          strokeLinejoin="round"
          strokeWidth="2.5"
          vectorEffect="non-scaling-stroke"
        />
        <polyline
          fill="none"
          points={chart.right}
          stroke="#d799ff"
          strokeLinejoin="round"
          strokeWidth="2.5"
          vectorEffect="non-scaling-stroke"
        />
        <g transform={`translate(${LEFT + 8} ${TOP + 12})`}>
          <rect width="12" height="4" y="-3" fill="#66c0f4" />
          <text x="19" y="2" fill="white" fontSize="13">
            {strings.trackpadMetricsLeft}
          </text>
          <rect width="12" height="4" x="76" y="-3" fill="#d799ff" />
          <text x="95" y="2" fill="white" fontSize="13">
            {strings.trackpadMetricsRight}
          </text>
        </g>
      </svg>
    </div>
  );
};
