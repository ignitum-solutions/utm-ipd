import { useId, useState } from "react";
import type { Result } from "./api";
import { opponentLabel } from "./opponents";

const statistics = [
  "Minimum",
  "First quartile",
  "Median",
  "Third quartile",
  "Maximum",
];

export function summarizeScores(values: number[]) {
  if (!values.length || !values.every(Number.isFinite)) return null;
  const sorted = [...values].sort((a, b) => a - b);
  // Quartiles linearly interpolate between sorted repetition scores.
  return [0, 0.25, 0.5, 0.75, 1].map((q) => {
    const position = (sorted.length - 1) * q;
    const low = Math.floor(position);
    return (
      sorted[low] +
      (position - low) * ((sorted[low + 1] ?? sorted[low]) - sorted[low])
    );
  });
}

export function scoreScale(values: number[], fit: boolean) {
  const finite = values.filter(Number.isFinite);
  const minimum = finite.length ? Math.min(...finite) : 0;
  const maximum = finite.length ? Math.max(...finite) : 5;
  const padding = Math.max((maximum - minimum) * 0.08, 0.02);
  const low = fit ? minimum - padding : Math.min(0, minimum);
  const high = fit ? maximum + padding : Math.max(5, maximum);
  const magnitude = 10 ** Math.floor(Math.log10((high - low) / 5));
  const step =
    [1, 2, 5, 10].find((n) => n * magnitude >= (high - low) / 5)! * magnitude;
  const start = Math.floor(low / step) * step;
  const end = Math.ceil(high / step) * step;
  const ticks = Array.from(
    { length: Math.round((end - start) / step) + 1 },
    (_, i) => start + i * step,
  );
  return { start, end, ticks };
}

function number(value: number) {
  return value.toLocaleString("en-US", { maximumFractionDigits: 6 });
}

function ScoreRow({
  name,
  values,
  scale,
}: {
  name: string;
  values: number[];
  scale: ReturnType<typeof scoreScale>;
}) {
  const id = useId();
  const [preview, setPreview] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const summary = summarizeScores(values);
  if (!summary)
    return <p className="muted">{name}: No repetition scores available.</p>;
  const x = (value: number) =>
    12 + ((value - scale.start) / (scale.end - scale.start)) * 576;
  const visible = preview || expanded;
  const identical = summary[0] === summary[4];
  return (
    <div
      className="score-row"
      onMouseEnter={() => setPreview(true)}
      onMouseLeave={() => setPreview(false)}
    >
      <button
        type="button"
        className="score-row-button"
        aria-label={`${name}: score distribution`}
        aria-expanded={expanded}
        aria-controls={id}
        aria-describedby={visible ? `${id}-statistics` : undefined}
        onFocus={() => setPreview(true)}
        onBlur={() => setPreview(false)}
        onClick={() => {
          setExpanded(!expanded);
          setPreview(false);
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setPreview(false);
            setExpanded(false);
          }
        }}
      >
        <span className="score-name">{name}</span>
        <svg viewBox="0 0 600 42" preserveAspectRatio="none" aria-hidden="true">
          {scale.ticks.map((tick) => (
            <line
              className="grid-line"
              key={tick}
              x1={x(tick)}
              x2={x(tick)}
              y1="0"
              y2="42"
            />
          ))}
          <g className="score-marks">
            <line x1={x(summary[0])} x2={x(summary[4])} y1="21" y2="21" />
            {[summary[0], summary[4]].map((value, i) => (
              <line key={i} x1={x(value)} x2={x(value)} y1="15" y2="27" />
            ))}
            {!identical && (
              <rect
                x={x(summary[1])}
                y="11"
                width={x(summary[3]) - x(summary[1])}
                height="20"
              />
            )}
            <line x1={x(summary[2])} x2={x(summary[2])} y1="10" y2="32" />
            {identical && <circle cx={x(summary[2])} cy="21" r="4" />}
          </g>
        </svg>
        <span className="score-median">
          <small>Median</small>
          <strong>{summary[2].toFixed(3)}</strong>
          <span aria-hidden="true">{expanded ? "−" : "+"}</span>
        </span>
      </button>
      {visible && (
        <div
          id={id}
          className={`score-values ${expanded ? "is-expanded" : ""}`}
          role={expanded ? "region" : "tooltip"}
          aria-label={`${name}: repetition statistics`}
        >
          <strong>{name}</strong>
          <dl id={`${id}-statistics`}>
            <div>
              <dt>Repetitions</dt>
              <dd>{values.length}</dd>
            </div>
            {summary.map((value, i) => (
              <div key={i}>
                <dt>{statistics[i]}</dt>
                <dd>{number(value)}</dd>
              </div>
            ))}
          </dl>
          {values.length === 1 ? (
            <p>One repetition: spread cannot be assessed.</p>
          ) : identical ? (
            <p>
              All repetition scores are equal; the box collapses to a single
              marker.
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}

export function ScoreDistribution({ result }: { result: Result }) {
  const id = useId();
  const [fit, setFit] = useState(false);
  const scores = result.scores ?? [];
  const scale = scoreScale(scores.flat(), fit);
  return (
    <section
      className="chart score-distribution"
      aria-labelledby={`${id}-title`}
    >
      <h3 id={`${id}-title`}>Score distribution</h3>
      <p className="muted">
        Each observation is one repetition’s mean payoff per turn against the
        other players. Self-play is excluded.
      </p>
      <div className="score-toolbar">
        <p>Box: middle 50% · Line: median · Whiskers: minimum to maximum</p>
        <label>
          <input
            type="checkbox"
            checked={fit}
            onChange={(event) => setFit(event.target.checked)}
          />
          Fit scale to observed scores
        </label>
      </div>
      <p className="muted">
        Hover or focus a row for values; click or tap to keep them open. A
        single marker means all repetition scores are equal.
      </p>
      <div
        className="score-axis"
        aria-label={`Shared payoff scale: ${number(scale.start)} to ${number(scale.end)}`}
      >
        <span>Strategy</span>
        <div>
          <div className="score-ticks">
            {scale.ticks.map((tick) => (
              <span
                key={tick}
                style={{
                  left: `${2 + ((tick - scale.start) / (scale.end - scale.start)) * 96}%`,
                }}
              >
                {number(tick)}
              </span>
            ))}
          </div>
          <span className="score-axis-title">
            Mean payoff per turn{" "}
            {fit ? "(observed range)" : "(full payoff range)"}
          </span>
        </div>
        <span>Median</span>
      </div>
      {(result.players ?? []).map((name, i) => (
        <ScoreRow
          key={i}
          name={`${i + 1}. ${opponentLabel(name)}`}
          values={scores[i] ?? []}
          scale={scale}
        />
      ))}
      <p className="muted score-footnote">
        Spread is across repetitions of this opponent field, not across
        opponents or a confidence interval. Quartiles use linear interpolation.
        Medians are shown to three decimals; details use up to six. Downloads
        retain precision.
      </p>
    </section>
  );
}
