import { lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  DEFAULT_CONFIG,
  csv,
  download,
  jsonHeaders,
  payload,
  readEvents,
  responseError,
} from "./api";
import type { Catalogue, Config, Result, RunKind, StreamEvent } from "./api";
import { LineChart, TournamentCharts } from "./charts";
import { RESEARCH } from "./research";
import type { ResearchPage } from "./research";
import OpponentPicker from "./OpponentPicker";
import { opponentLabel } from "./opponents";

type Page = ResearchPage;
const ModelGuide = lazy(() => import("./ModelGuide"));
const PAGES: { id: Page; label: string; number: string }[] = [
  { id: "tournament", label: "IPD Tournament", number: "01" },
  { id: "moran", label: "Moran Process", number: "02" },
  { id: "trust", label: "Trust Game", number: "03" },
  { id: "sweeps", label: "Parameter Sweeps", number: "04" },
  { id: "guide", label: "The Model", number: "05" },
];
function isRun(page: Page): page is RunKind {
  return ["tournament", "moran", "trust"].includes(page);
}
function initialPage(): Page {
  const value = new URLSearchParams(location.search).get("view");
  return PAGES.find((p) => p.id === value)?.id ?? "tournament";
}
const LEAVE_MESSAGE =
  "Leaving disconnects this run. Its progress and result will not be recoverable. Server execution may continue until its time limit. Do you want to leave?";

function NumberField({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (n: number) => void;
}) {
  return (
    <label className="number-field">
      <span>{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        required
      />
    </label>
  );
}
function Slider({
  label,
  symbol,
  value,
  max = 1,
  min = 0,
  step = 0.01,
  help,
  onChange,
}: {
  label: string;
  symbol: string;
  value: number;
  max?: number;
  min?: number;
  step?: number;
  help: string;
  onChange: (n: number) => void;
}) {
  return (
    <label className="slider-field">
      <span>
        <b>{symbol}</b> {label}
        <output>{value.toFixed(step < 0.01 ? 3 : 2)}</output>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <small>{help}</small>
    </label>
  );
}
function Dialog({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <h2>{title}</h2>
      {children}
    </dialog>
  );
}

function ResultView({ result }: { result: Result }) {
  const [copyStatus, setCopyStatus] = useState("Copy summary");
  const rows =
    result.leaderboard ??
    result.series?.map((value, index) =>
      result.kind === "trust"
        ? {
            Round: index + 1,
            Trust: value,
            Investment: result.investments?.[index] ?? null,
            "Net payoff": result.payoffs?.[index] ?? null,
            "Cumulative payoff": result.cumulative?.[index] ?? null,
          }
        : { Generation: index, "UTM share": value },
    ) ??
    [];
  const summary = result.summary
    ? Object.entries(result.summary)
        .map(([name, value]) => `${name}: ${value ?? "Not reached"}`)
        .join("\n")
    : csv(rows);
  return (
    <section className="results" aria-label="Simulation results">
      <div className="section-heading">
        <div>
          <p className="eyebrow">OBSERVATIONS</p>
          <h2>Run results</h2>
        </div>
        <span className="success-badge">✓ Run complete</span>
      </div>
      <div className="result-actions">
        <button
          onClick={() =>
            download(
              `utm-${result.kind}.csv`,
              csv(rows),
              "text/csv;charset=utf-8",
            )
          }
        >
          ↓ Download CSV
        </button>
        <button
          onClick={() =>
            download(
              `utm-${result.kind}-reproduce.json`,
              JSON.stringify(result, null, 2),
              "application/json",
            )
          }
        >
          ↓ Results + settings
        </button>
        <button
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(summary);
              setCopyStatus("Copied");
            } catch {
              setCopyStatus("Use the copy-ready text below");
            }
          }}
        >
          {copyStatus}
        </button>
      </div>
      <details>
        <summary>Exact settings for this run</summary>
        <pre>{JSON.stringify(result.config, null, 2)}</pre>
      </details>
      {result.metadata && (
        <details>
          <summary>Run provenance and protocol</summary>
          <pre>{JSON.stringify(result.metadata, null, 2)}</pre>
        </details>
      )}
      {result.leaderboard && (
        <section className="chart">
          <h3>Leaderboard</h3>
          <p className="muted">
            Display values are rounded to three decimals; downloads retain
            precision. Equal exact means share a rank. Player index identifies
            the input slot.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {Object.keys(result.leaderboard[0] ?? {}).map((key) => (
                    <th key={key}>{key}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.leaderboard.map((row, i) => (
                  <tr key={i}>
                    {Object.entries(row).map(([key, value]) => (
                      <td key={key}>
                        {typeof value === "number"
                          ? Number.isInteger(value)
                            ? value
                            : value.toFixed(3)
                          : key === "Player" && typeof value === "string"
                            ? opponentLabel(value)
                            : (value ?? "—")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {result.summary && (
        <div className="metric-grid">
          {Object.entries(result.summary).map(([name, value]) => (
            <div className="metric" key={name}>
              <span>{name}</span>
              <strong>
                {value === null
                  ? "Not reached"
                  : Number.isInteger(value)
                    ? value
                    : value.toFixed(3)}
              </strong>
            </div>
          ))}
        </div>
      )}
      {result.kind === "tournament" ? (
        <TournamentCharts result={result} />
      ) : (
        <div className="chart-grid">
          <LineChart
            title={
              result.kind === "moran"
                ? "UTM population share"
                : "Trust trajectory"
            }
            values={result.series ?? []}
            firstStep={result.kind === "trust" ? 1 : 0}
            unit={result.kind === "moran" ? "generations" : "rounds"}
          />
          {result.cumulative && (
            <LineChart
              title="Cumulative payoff"
              values={result.cumulative}
              firstStep={1}
              unit="rounds"
            />
          )}
        </div>
      )}
      <details>
        <summary>Copy-ready summary</summary>
        <textarea
          aria-label="Copy-ready summary"
          readOnly
          value={summary}
          rows={8}
        />
      </details>
    </section>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>(initialPage);
  const [catalogue, setCatalogue] = useState<Catalogue>();
  const [loadError, setLoadError] = useState("");
  const [retry, setRetry] = useState(0);
  const [configs, setConfigs] = useState<Record<RunKind, Config>>({
    tournament: { ...DEFAULT_CONFIG },
    moran: { ...DEFAULT_CONFIG },
    trust: {
      ...DEFAULT_CONFIG,
      theta: 0.5,
      alpha_pos: 0.05,
      alpha_neg: 0.5,
      delta: 0.55,
      threshold: 0.45,
      rounds: 50,
    },
  });
  const [results, setResults] = useState<Partial<Record<RunKind, Result>>>({});
  const [parametersOpen, setParametersOpen] = useState<
    Record<RunKind, boolean>
  >({ tournament: true, moran: true, trust: true });
  const [resultsOpen, setResultsOpen] = useState<Record<RunKind, boolean>>({
    tournament: true,
    moran: true,
    trust: true,
  });
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<StreamEvent>();
  const [error, setError] = useState("");
  const [startedAt, setStartedAt] = useState(0);
  const [lastUpdate, setLastUpdate] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [pendingPage, setPendingPage] = useState<Page | "disconnect">();
  const [explanation, setExplanation] = useState("");
  const [explanationError, setExplanationError] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [suggestMessage, setSuggestMessage] = useState("");
  const [savingSuggestion, setSavingSuggestion] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const parameterPanel = useRef<HTMLDetailsElement>(null);
  const runPanel = useRef<HTMLElement>(null);
  const cfg = configs[isRun(page) ? page : "tournament"];
  const update = <K extends keyof Config>(key: K, value: Config[K]) => {
    if (isRun(page))
      setConfigs((old) => ({ ...old, [page]: { ...old[page], [key]: value } }));
  };
  useEffect(() => {
    const abort = new AbortController();
    setLoadError("");
    fetch("/api/catalogue", { signal: abort.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(await responseError(response));
        setCatalogue(await response.json());
      })
      .catch((e) => {
        if (!abort.signal.aborted)
          setLoadError(e.message || "The research service is unavailable.");
      });
    return () => abort.abort();
  }, [retry]);
  useEffect(() => {
    if (page !== "guide" || explanation) return;
    const abort = new AbortController();
    setExplanationError(false);
    fetch("/api/explanation", { signal: abort.signal })
      .then((response) => {
        if (!response.ok) throw new Error();
        return response.text();
      })
      .then(setExplanation)
      .catch(() => {
        if (!abort.signal.aborted) setExplanationError(true);
      });
    return () => abort.abort();
  }, [page, explanation, retry]);
  useEffect(() => {
    if (!running) return;
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const pageHide = () => controller.current?.abort();
    window.addEventListener("beforeunload", beforeUnload);
    window.addEventListener("pagehide", pageHide);
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      window.removeEventListener("pagehide", pageHide);
      clearInterval(timer);
    };
  }, [running]);
  useEffect(
    () => () => {
      controller.current?.abort();
    },
    [],
  );
  useEffect(() => {
    if (!running) return;
    runPanel.current?.scrollIntoView({ block: "start" });
    runPanel.current?.focus({ preventScroll: true });
  }, [running]);

  function showParameters() {
    if (!isRun(page)) return;
    setParametersOpen((old) => ({ ...old, [page]: true }));
    requestAnimationFrame(() => {
      parameterPanel.current?.scrollIntoView({ block: "start" });
      parameterPanel.current
        ?.querySelector("summary")
        ?.focus({ preventScroll: true });
    });
  }

  function navigate(next: Page) {
    if (next === page) return;
    if (controller.current) {
      setPendingPage(next);
      return;
    }
    changePage(next);
  }
  function changePage(next: Page) {
    setPage(next);
    setError("");
    const url = new URL(location.href);
    url.searchParams.set("view", next);
    history.replaceState(null, "", url);
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  function leaveRun() {
    controller.current?.abort();
    controller.current = null;
    setRunning(false);
    setProgress(undefined);
    if (pendingPage && pendingPage !== "disconnect") changePage(pendingPage);
    else
      setError(
        "Disconnected. The result cannot be recovered; server execution may continue until its limit.",
      );
    setPendingPage(undefined);
  }
  async function run() {
    if (!isRun(page) || controller.current || !catalogue) return;
    const kind = page,
      abort = new AbortController();
    controller.current = abort;
    setRunning(true);
    setError("");
    setProgress({
      type: "started",
      phase: "Connecting to the research service",
    });
    setParametersOpen((old) => ({ ...old, [kind]: false }));
    setResultsOpen((old) => ({ ...old, [kind]: true }));
    setResults((old) => ({ ...old, [kind]: undefined }));
    const start = Date.now();
    setStartedAt(start);
    setLastUpdate(start);
    setNow(start);
    try {
      const body = JSON.stringify(payload(kind, cfg));
      const headers = await jsonHeaders(body);
      if (abort.signal.aborted) return;
      const response = await fetch(`/api/run/${kind}`, {
        method: "POST",
        headers,
        body,
        signal: abort.signal,
      });
      if (!response.ok) throw new Error(await responseError(response));
      if (!response.body)
        throw new Error(
          "This browser cannot receive streamed results. Please use a current browser.",
        );
      await readEvents(response.body, (event) => {
        if (controller.current !== abort) return;
        setLastUpdate(Date.now());
        if (event.type !== "heartbeat") setProgress(event);
        if (event.type === "result" && event.result)
          setResults((old) => ({ ...old, [kind]: event.result }));
      });
    } catch (e) {
      if (controller.current === abort && !abort.signal.aborted) {
        setError(
          e instanceof Error ? e.message : "The simulation could not finish.",
        );
        setParametersOpen((old) => ({ ...old, [kind]: true }));
      }
    } finally {
      if (controller.current === abort) {
        controller.current = null;
        setRunning(false);
      }
    }
  }
  async function submitSuggestion(form: HTMLFormElement) {
    setSavingSuggestion(true);
    setSuggestMessage("");
    try {
      const data = new FormData(form),
        { seed: _seed, ...parameters } = payload("trust", cfg);
      const body = JSON.stringify({
        ...Object.fromEntries(
          [
            "theta",
            "alpha_pos",
            "alpha_neg",
            "delta",
            "threshold",
            "variant",
          ].map((key) => [key, parameters[key]]),
        ),
        name: data.get("name"),
        creator: data.get("creator"),
        description: data.get("description"),
      });
      const response = await fetch("/api/suggestions", {
        method: "POST",
        headers: await jsonHeaders(body),
        body,
      });
      if (!response.ok) throw new Error(await responseError(response));
      setSuggestMessage("Your suggestion was saved for review. Thank you.");
      form.reset();
    } catch (e) {
      setSuggestMessage(
        e instanceof Error ? e.message : "Please try again later.",
      );
    } finally {
      setSavingSuggestion(false);
    }
  }
  const currentResult = isRun(page) ? results[page] : undefined;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="https://ignitumsolutions.com"
          target="_blank"
          rel="noreferrer"
        >
          <img
            src="/assets/IgnitumSolutions_RGB_Icon.png"
            alt="Ignitum Solutions"
          />
          <span>
            IGNITUM<small>RESEARCH LAB</small>
          </span>
        </a>
        <div className="sidebar-caption">UNIVERSAL TRUST MODEL</div>
        <nav aria-label="Research tools">
          {PAGES.map((item) => (
            <button
              key={item.id}
              className={page === item.id ? "nav-item active" : "nav-item"}
              onClick={() => navigate(item.id)}
              aria-current={page === item.id ? "page" : undefined}
            >
              <span>{item.number}</span>
              {item.label}
              <span className="nav-arrow">↗</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="status-dot" /> Research simulations
          <a
            href="https://github.com/ignitum-solutions/utm-ipd"
            target="_blank"
            rel="noreferrer"
          >
            Source, methods & local setup ↗
          </a>
          <small>Code: MIT · Documentation: CC BY 4.0</small>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            UTM <span className="slash">/</span>{" "}
            {PAGES.find((p) => p.id === page)?.label}
          </span>
          <span className="topbar-badge">INTERACTIVE RESEARCH</span>
        </header>
        <div className="workspace">
          <section className="hero">
            <p className="eyebrow">UNIVERSAL TRUST MODEL / EXPERIMENTS</p>
            <h1>{RESEARCH[page].title}</h1>
            <p>{RESEARCH[page].question}</p>
          </section>
          {page !== "guide" && (
            <details className="study-context">
              <summary>Study design, measurements, and assumptions</summary>
              <div className="study-grid">
                <section>
                  <h2>Study design</h2>
                  <p>{RESEARCH[page].design}</p>
                </section>
                <section>
                  <h2>Measurements</h2>
                  <p>{RESEARCH[page].measures}</p>
                </section>
                <section>
                  <h2>Protocol and assumptions</h2>
                  <p>{RESEARCH[page].assumptions}</p>
                </section>
              </div>
            </details>
          )}
          {loadError && (
            <div className="notice error" role="alert">
              Could not connect to the research service. {loadError}{" "}
              <button onClick={() => setRetry((n) => n + 1)}>Try again</button>
            </div>
          )}
          {isRun(page) && (
            <>
              <section
                ref={runPanel}
                className="run-workspace"
                aria-label="Run status and results"
                tabIndex={-1}
              >
                <div className="run-bar">
                  <div>
                    <p className="eyebrow">EXECUTION</p>
                    <h2>Simulation run</h2>
                    <p>
                      {running
                        ? "Execution in progress. Keep this page open for status and results."
                        : currentResult
                          ? "Completed observations are retained while you configure the next run."
                          : "Review the parameters below, then submit a simulation."}
                    </p>
                  </div>
                  <div className="run-actions">
                    <button
                      type="button"
                      onClick={showParameters}
                      aria-controls="run-parameters"
                    >
                      {running ? "View parameters ↓" : "Edit parameters ↓"}
                    </button>
                    <button
                      className="primary-button"
                      type="submit"
                      form="simulation-parameters-form"
                      disabled={running || !catalogue}
                    >
                      {running
                        ? "Running…"
                        : catalogue
                          ? "Run simulation →"
                          : "Connecting…"}
                    </button>
                  </div>
                </div>
                {running && (
                  <section
                    className="progress-panel"
                    aria-label="Simulation progress"
                  >
                    <div className="section-heading">
                      <strong aria-live="polite">
                        {progress?.phase ?? "Running simulation"}
                      </strong>
                      <span>
                        {Math.max(0, Math.floor((now - startedAt) / 1000))}s
                        elapsed
                      </span>
                    </div>
                    <progress
                      max="100"
                      value={progress?.percent ?? undefined}
                      aria-label="Current simulation phase completion"
                    />
                    <div className="progress-meta">
                      <span>
                        {progress?.completed !== undefined && progress?.total
                          ? `${progress.completed} / ${progress.total} work units (${progress.percent}%)`
                          : "Waiting for the next measured update"}{" "}
                        · Last update{" "}
                        {Math.max(0, Math.floor((now - lastUpdate) / 1000))}s
                        ago
                      </span>
                      <button
                        className="text-button"
                        onClick={() => setPendingPage("disconnect")}
                      >
                        Disconnect run
                      </button>
                    </div>
                    {now - lastUpdate > 15000 && (
                      <p role="status">
                        No recent updates. Keep this page open; do not start a
                        duplicate run.
                      </p>
                    )}
                  </section>
                )}
                {error && (
                  <div className="notice error" role="alert">
                    {error}
                  </div>
                )}
                {currentResult && !running && (
                  <>
                    <div className="results-toolbar">
                      <span>
                        Completed run · seed {String(currentResult.config.seed)}
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          setResultsOpen((old) => ({
                            ...old,
                            [page]: !old[page],
                          }))
                        }
                        aria-expanded={resultsOpen[page]}
                        aria-controls="run-results"
                      >
                        {resultsOpen[page] ? "Hide results" : "Show results"}
                      </button>
                    </div>
                    <div id="run-results" hidden={!resultsOpen[page]}>
                      <ResultView
                        key={JSON.stringify(currentResult.config)}
                        result={currentResult}
                      />
                    </div>
                  </>
                )}
                {!currentResult && !running && !error && (
                  <p className="run-empty">
                    No observations yet. Results and downloads will appear here
                    after the simulation completes.
                  </p>
                )}
              </section>
              <details
                ref={parameterPanel}
                key={page}
                id="run-parameters"
                className="parameter-disclosure"
                open={parametersOpen[page]}
                onToggle={(event) => {
                  const open = event.currentTarget.open;
                  setParametersOpen((old) =>
                    old[page] === open ? old : { ...old, [page]: open },
                  );
                }}
              >
                <summary>
                  <span>Run parameters</span>
                  <span className="parameter-summary">
                    θ {cfg.theta} · α⁺ {cfg.alpha_pos} · α⁻ {cfg.alpha_neg} · δ{" "}
                    {cfg.delta} · τ {cfg.threshold} · seed {cfg.seed}
                  </span>
                  <span className="parameter-state">
                    {parametersOpen[page] ? "Collapse" : "Expand"}
                  </span>
                </summary>
                {running && (
                  <p className="parameter-lock-note">
                    Parameters are fixed for the active run. They can be edited
                    when execution finishes.
                  </p>
                )}
                <form
                  id="simulation-parameters-form"
                  onInvalidCapture={() =>
                    setParametersOpen((old) => ({ ...old, [page]: true }))
                  }
                  onSubmit={(e) => {
                    e.preventDefault();
                    void run();
                  }}
                >
                  <div className="experiment-grid">
                    <section className="panel">
                      <div className="section-heading">
                        <div>
                          <p className="eyebrow">01 / DEFINE THE AGENT</p>
                          <h2>Trust parameters</h2>
                        </div>
                        <span className="small-tag">UTM</span>
                      </div>
                      <fieldset disabled={running}>
                        <label className="select-field">
                          Strategy variant
                          <select
                            value={cfg.variant}
                            onChange={(e) => update("variant", e.target.value)}
                            disabled={page === "trust"}
                          >
                            {(catalogue?.variants ?? ["TFT"]).map((name) => (
                              <option key={name}>{name}</option>
                            ))}
                          </select>
                        </label>
                        {page === "trust" && (
                          <p className="field-note">
                            This game uses the trust meter directly; the IPD
                            strategy variant is not used.
                          </p>
                        )}
                        {page !== "trust" && cfg.variant === "TFT→WSLS" && (
                          <p className="field-note">
                            The hybrid switches permanently to WSLS when trust
                            is greater than 0.55, including the first decision
                            if initial trust exceeds 0.55. The separate
                            cooperation threshold still applies.
                          </p>
                        )}
                        <Slider
                          label="Initial trust"
                          symbol="θ"
                          value={cfg.theta}
                          help="Initial trust value before the first interaction."
                          onChange={(v) => update("theta", v)}
                        />
                        <Slider
                          label="Positive learning rate"
                          symbol="α⁺"
                          value={cfg.alpha_pos}
                          max={0.5}
                          step={0.001}
                          help="Learning rate when the signed reward exceeds current trust."
                          onChange={(v) => update("alpha_pos", v)}
                        />
                        <Slider
                          label="Negative learning rate"
                          symbol="α⁻"
                          value={cfg.alpha_neg}
                          step={0.001}
                          help="Learning rate when the signed reward is at or below current trust."
                          onChange={(v) => update("alpha_neg", v)}
                        />
                        <Slider
                          label="Betrayal ramp"
                          symbol="δ"
                          value={cfg.delta}
                          help="Cumulative update multiplier after rewards below current trust."
                          onChange={(v) => update("delta", v)}
                        />
                        <Slider
                          label="Cooperation threshold"
                          symbol="τ"
                          value={cfg.threshold}
                          min={0.05}
                          help="Trust threshold used by the selected decision rule."
                          onChange={(v) => update("threshold", v)}
                        />
                      </fieldset>
                      <button
                        type="button"
                        className="text-button"
                        onClick={() => navigate("guide")}
                      >
                        Model definitions and update rule ↗
                      </button>
                    </section>
                    <section className="panel">
                      <div className="section-heading">
                        <div>
                          <p className="eyebrow">02 / SET THE ENVIRONMENT</p>
                          <h2>
                            {page === "tournament"
                              ? "Tournament configuration"
                              : page === "moran"
                                ? "Population configuration"
                                : "Investment configuration"}
                          </h2>
                        </div>
                      </div>
                      <fieldset disabled={running}>
                        {page === "tournament" && (
                          <>
                            <OpponentPicker
                              opponents={catalogue?.opponents ?? cfg.opponents}
                              selected={cfg.opponents}
                              onChange={(names) => update("opponents", names)}
                            />
                            <details className="settings-details">
                              <summary>
                                UTM personalities{" "}
                                <span>{cfg.presets.length} selected</span>
                              </summary>
                              <div className="preset-list">
                                {Object.entries(catalogue?.presets ?? {}).map(
                                  ([name, preset]) => (
                                    <label key={name}>
                                      <input
                                        type="checkbox"
                                        checked={cfg.presets.includes(name)}
                                        onChange={(e) =>
                                          update(
                                            "presets",
                                            e.target.checked
                                              ? [...cfg.presets, name]
                                              : cfg.presets.filter(
                                                  (n) => n !== name,
                                                ),
                                          )
                                        }
                                      />
                                      <span>
                                        <b>{name}</b>
                                        <small>{preset.description}</small>
                                        <small>
                                          {preset.creator} · θ {preset.theta} ·
                                          α⁺ {preset.alpha_pos} · α⁻{" "}
                                          {preset.alpha_neg} · δ {preset.delta}{" "}
                                          · τ {preset.tau}
                                        </small>
                                      </span>
                                    </label>
                                  ),
                                )}
                              </div>
                            </details>
                            <div className="input-grid">
                              <NumberField
                                label="Rounds per match"
                                value={cfg.rounds}
                                min={1}
                                max={1000}
                                onChange={(v) => update("rounds", v)}
                              />
                              <NumberField
                                label="Repetitions"
                                value={cfg.repetitions}
                                min={1}
                                max={100}
                                onChange={(v) => update("repetitions", v)}
                              />
                              <NumberField
                                label="Noise (%)"
                                value={cfg.noise_pct}
                                min={0}
                                max={20}
                                onChange={(v) => update("noise_pct", v)}
                              />
                              <NumberField
                                label="Random seed"
                                value={cfg.seed}
                                min={0}
                                max={9999}
                                onChange={(v) => update("seed", v)}
                              />
                            </div>
                            <details className="settings-details">
                              <summary>Extra opponent</summary>
                              <label className="select-field">
                                Approved strategy
                                <select
                                  value={cfg.extra_opponent}
                                  onChange={(e) =>
                                    update("extra_opponent", e.target.value)
                                  }
                                >
                                  {(catalogue?.extra_opponents ?? ["None"]).map(
                                    (name) => (
                                      <option key={name}>{name}</option>
                                    ),
                                  )}
                                </select>
                              </label>
                              <label className="checkbox-field">
                                <input
                                  type="checkbox"
                                  checked={cfg.noise_wrap}
                                  disabled={cfg.extra_opponent === "None"}
                                  onChange={(e) =>
                                    update("noise_wrap", e.target.checked)
                                  }
                                />
                                Add 5% noise wrapper
                              </label>
                            </details>
                          </>
                        )}
                        {page === "moran" && (
                          <>
                            <p className="environment-intro">
                              Start with <strong>one UTM agent</strong> and a
                              population of cooperators. Each generation selects
                              an agent to reproduce based on its performance.
                            </p>
                            <div className="input-grid">
                              <NumberField
                                label="Population size"
                                value={cfg.population}
                                min={5}
                                max={50}
                                onChange={(v) => update("population", v)}
                              />
                              <NumberField
                                label="Maximum generations"
                                value={cfg.generations}
                                min={1}
                                max={1000}
                                onChange={(v) => update("generations", v)}
                              />
                              <NumberField
                                label="Rounds per match"
                                value={cfg.rounds}
                                min={1}
                                max={1000}
                                onChange={(v) => update("rounds", v)}
                              />
                              <NumberField
                                label="Random seed"
                                value={cfg.seed}
                                min={0}
                                max={9999}
                                onChange={(v) => update("seed", v)}
                              />
                            </div>
                            <p className="field-note">
                              The run finishes early if one strategy takes over
                              the whole population. Progress measures the
                              generation limit, not the chance of fixation.
                            </p>
                          </>
                        )}
                        {page === "trust" && (
                          <>
                            <p className="environment-intro">
                              An investment is <strong>tripled</strong> before
                              the partner returns a fraction. The net payoff
                              determines the signed trust reward. Zero payoff,
                              including no investment, is treated as a positive
                              reward in this experiment.
                            </p>
                            <div className="input-grid">
                              <NumberField
                                label="Rounds"
                                value={cfg.rounds}
                                min={1}
                                max={500}
                                onChange={(v) => update("rounds", v)}
                              />
                              <NumberField
                                label="Send amount"
                                value={cfg.send}
                                min={0}
                                max={10}
                                step={0.5}
                                onChange={(v) => update("send", v)}
                              />
                              <NumberField
                                label="Good return fraction"
                                value={cfg.return_good}
                                min={0}
                                max={1}
                                step={0.05}
                                onChange={(v) => update("return_good", v)}
                              />
                              <NumberField
                                label="Betrayal return fraction"
                                value={cfg.return_bad}
                                min={0}
                                max={1}
                                step={0.05}
                                onChange={(v) => update("return_bad", v)}
                              />
                              <NumberField
                                label="Betrayal probability"
                                value={cfg.betrayal_probability}
                                min={0}
                                max={1}
                                step={0.05}
                                onChange={(v) =>
                                  update("betrayal_probability", v)
                                }
                              />
                              <NumberField
                                label="Random seed"
                                value={cfg.seed}
                                min={0}
                                max={9999}
                                onChange={(v) => update("seed", v)}
                              />
                            </div>
                          </>
                        )}
                      </fieldset>
                      {catalogue?.submissions_enabled && (
                        <button
                          className="text-button"
                          type="button"
                          disabled={running}
                          onClick={() => {
                            setSuggestMessage("");
                            setSuggesting(true);
                          }}
                        >
                          Suggest these UTM parameters as a preset ↗
                        </button>
                      )}
                    </section>
                  </div>
                  <div className="parameter-actions">
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => {
                        runPanel.current?.scrollIntoView({ block: "start" });
                        runPanel.current?.focus({ preventScroll: true });
                      }}
                    >
                      ↑ Back to run status and results
                    </button>
                  </div>
                </form>
              </details>
            </>
          )}
          {page === "sweeps" && (
            <section className="panel reading">
              <h2>Local sweep protocol</h2>
              <p>
                The public demo supports individual runs. The local research
                tools let you explore grids or random combinations of trust
                parameters and IPD reward mappings.
              </p>
              <ol>
                <li>
                  Download this repository and follow the local setup in the
                  README.
                </li>
                <li>
                  Install the optional research tools with{" "}
                  <code>poetry install --with research</code>.
                </li>
                <li>Launch the sweep tool with the command below.</li>
              </ol>
              <pre>
                ENABLE_SWEEP_UI=true poetry run streamlit run
                dash/pages/01_IPD_Mini_Sweep.py
              </pre>
              <p>
                The legacy sweep interface remains available for
                reproducibility. Its safeguards limit a sweep to 32
                combinations, 100 rounds, 5 repetitions, and 10 players.
              </p>
              <h3>Reference IPD reward mapping</h3>
              <table>
                <thead>
                  <tr>
                    <th>Your move / partner’s move</th>
                    <th>Signed trust reward</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["Cooperate / Cooperate", "+1.0"],
                    ["Defect / Cooperate", "+0.5"],
                    ["Defect / Defect", "−0.2"],
                    ["Cooperate / Defect", "−1.0"],
                  ].map(([a, b]) => (
                    <tr key={a}>
                      <td>{a}</td>
                      <td>{b}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p>
                These values update the trust meter; they are separate from the
                Prisoner’s Dilemma game payoffs.
              </p>
              <h3>Current tournament reference settings</h3>
              <pre>
                {JSON.stringify(
                  payload("tournament", configs.tournament),
                  null,
                  2,
                )}
              </pre>
            </section>
          )}
          {page === "guide" && (
            <article className="panel reading">
              {explanation ? (
                <Suspense
                  fallback={<p role="status">Preparing the model guide…</p>}
                >
                  <ModelGuide source={explanation} />
                </Suspense>
              ) : explanationError ? (
                <div role="alert">
                  The model guide could not load.{" "}
                  <button onClick={() => setRetry((n) => n + 1)}>
                    Try again
                  </button>
                </div>
              ) : (
                <p role="status">Loading the model guide…</p>
              )}
            </article>
          )}
          <footer>
            <span>Universal Trust Model × Iterated Prisoner’s Dilemma</span>
            <p>
              A research prototype by Ryan Carlisle · Ignitum Solutions. Built
              with Axelrod-Python. Code MIT; model documentation CC BY 4.0.
            </p>
            <p>
              For research use. Do not submit confidential or sensitive
              information.
            </p>
            <a
              href="https://github.com/ignitum-solutions/utm-ipd"
              target="_blank"
              rel="noreferrer"
            >
              Local setup, source & citation ↗
            </a>
            {catalogue && <small>Build {catalogue.version.slice(0, 7)}</small>}
          </footer>
        </div>
      </main>
      {pendingPage && (
        <Dialog
          title="Leave this active run?"
          onClose={() => setPendingPage(undefined)}
        >
          <p>{LEAVE_MESSAGE}</p>
          <div className="dialog-actions">
            <button onClick={() => setPendingPage(undefined)} autoFocus>
              Stay here
            </button>
            <button className="danger-button" onClick={leaveRun}>
              Leave this run
            </button>
          </div>
        </Dialog>
      )}
      {suggesting && (
        <Dialog
          title="Suggest a personality preset"
          onClose={() => {
            if (!savingSuggestion) setSuggesting(false);
          }}
        >
          <p>
            Your current UTM parameters will be included. Suggestions are stored
            privately for review. Do not include confidential or sensitive
            information.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void submitSuggestion(e.currentTarget);
            }}
          >
            <label className="select-field">
              Preset name
              <input name="name" required maxLength={80} />
            </label>
            <label className="select-field">
              Creator / handle (optional)
              <input name="creator" maxLength={80} />
            </label>
            <label className="select-field">
              Research rationale and expected behavior
              <textarea name="description" required maxLength={2000} rows={4} />
            </label>
            {suggestMessage && <p role="status">{suggestMessage}</p>}
            <div className="dialog-actions">
              <button
                type="button"
                disabled={savingSuggestion}
                onClick={() => setSuggesting(false)}
              >
                Close
              </button>
              <button className="primary-button" disabled={savingSuggestion}>
                {savingSuggestion ? "Saving…" : "Submit for review"}
              </button>
            </div>
          </form>
        </Dialog>
      )}
    </div>
  );
}
