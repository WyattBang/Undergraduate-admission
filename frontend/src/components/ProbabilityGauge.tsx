import React from "react";

type Props = {
  probability: number;
  confidenceBand: "high" | "medium" | "low";
};

export default function ProbabilityGauge({ probability, confidenceBand }: Props) {
  const pct = Math.round(probability * 100);
  return (
    <div className="gauge-card">
      <div className="gauge-ring" style={{ ["--p" as string]: String(pct) }}>
        <div className="gauge-center">
          <div className="gauge-value">{pct}%</div>
          <div className="gauge-label">录取概率</div>
        </div>
      </div>
      <div className={`confidence ${confidenceBand}`}>可信度：{confidenceBand.toUpperCase()}</div>
    </div>
  );
}
