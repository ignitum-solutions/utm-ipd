# Universal Trust Model × Iterated Prisoner’s Dilemma

<p align="center">
  <img src="dash/static/IgnitumSolutions_RGB_Icon.png" width="100" alt="Ignitum Solutions">
</p>

An open research interface for exploring how trust changes through repeated
interactions. Compare UTM strategies in Prisoner’s Dilemma tournaments, follow
evolution in a Moran process, or explore an investment/Trust Game.

> **Interface migration — in development:** This branch moves the public
> interface from Streamlit to a React frontend with a streaming Python backend.
> The change supports efficient on-demand deployment, independent concurrent
> runs, and live progress synchronization. The Python model and research tools
> remain available. The hosted site may use the previous release until cutover.
> See [what changed and how to move](docs/INTERFACE_MIGRATION.md).

## Run the research interface on your computer

You do not need an AWS account or Docker. Local runs use your own computer.
The first setup downloads Python and JavaScript dependencies.

Install these prerequisites:

- **Python 3.13**
- **Node.js 22.12 or newer**, including npm
- **Poetry 2.2 or newer** for Python dependencies

From this repository's checkout, run:

```bash
poetry install
npm --prefix frontend ci
./run_local.sh
```

Open **http://127.0.0.1:5173**. Keep the terminal open; press **Ctrl+C** there to
stop the local application. If you are reading this on the migration branch,
check out that same branch before following these instructions.

On Windows, or if your shell cannot run the launcher, use:

```bash
poetry run python scripts/dev.py
```

The launcher starts both parts of the application: the browser interface on
port 5173 and the Python service on port 8000. If a port is already in use, stop
the other application using it and rerun the command. If `poetry` or `npm` is
not found, install the prerequisites above and reopen your terminal.

### Your first experiment

1. Open **IPD Tournament** and keep the default settings.
2. Click **Run simulation** and keep the page open while it runs.
3. Read measured progress and results above the parameters. The parameter panel
   collapses during execution; use View parameters or Edit parameters to reopen
   it. Results can also be hidden and reopened.
4. Use **Download CSV** for observations or **Results + settings** to save the
   complete output and the exact parameters used.

The same settings, seed, presets, and software versions allow you to repeat an
experiment. Changing a seed can change stochastic outcomes. Keep the lockfiles
with your research environment; separate releases can produce different results.

Each run streams its progress and result directly to your browser. There is no
background job history. Leaving or refreshing during a run displays a warning
where the browser supports it; you may lose access to the result. Closing a tab
cannot guarantee cancellation of a hosted Lambda invocation. A disconnected run
cannot be recovered or resumed automatically. Download results you want to keep.

The local interface accepts the same bounded requests as the hosted demo. For
larger experiments, use the Python tools below. The default request time limit
is four minutes, configurable with `MAX_RUN_SECONDS` up to 840 seconds; the
engine also checks workload size. Local concurrency defaults to two independent
runs. Additional requests receive a busy message rather than entering a queue.

## Python research tools

The core model in `utm/`, strategy implementations in `strategies/`, and
Axelrod-based runner in `tournaments/` are still Python modules. Run a tournament
without opening the web interface:

```bash
poetry run python main.py --rounds 200 --reps 30 --players utm_tft tft wsls alld allc random
```

The CLI does not apply the web demo's workload cap. Start small and increase
experiment size deliberately. You can also import `run_tournament` or
`TrustMeter` in your own scripts or notebooks.

### Optional parameter sweeps and previous interface

The existing local Streamlit research tools remain available for reproducibility
and parameter sweeps. Install their optional dependencies first:

```bash
poetry install --with research
ENABLE_SWEEP_UI=true poetry run streamlit run dash/pages/01_IPD_Mini_Sweep.py
```

Sweeps remain local-only and retain their execution safeguards. To open the
previous full dashboard:

```bash
poetry run streamlit run dash/00_IPD_Tournament.py
```

The original `Dockerfile` and `docker-compose.yaml` support this **legacy local
interface**, not the React research interface. Existing users can still run:

```bash
docker compose up --build
# Legacy dashboard: http://localhost:8501
```

`run_local.sh` now launches React and Python instead of Docker Compose. Its old
`--prune` and `--no-cache` flags are retired; use Docker's own commands when
working with the optional legacy interface.

## Recorded methods and reproducibility

Results contain observations and numerical summaries; the interface does not
perform or generate an interpretation of a completed run. Download Results +
settings for the effective protocol, resolved preset parameters, scoring game,
trust mapping, environment versions, engine revision, and source hashes.

Tournament scores use the same game payoffs for every player and exclude
self-play from leaderboard aggregates. Equal exact means share a rank.
Cooperation counts come from recorded non-self moves. Local sweep heatmaps
show the mean of sampled observations in each cell. Implementation details and
model assumptions are documented alongside the code and in the model guide.

For full move traces from the CLI, specify a seed and a CSV directory:

```bash
poetry run python main.py --players utm_tft alld --rounds 100 --reps 5 --seed 42 --csv-dir observations
```

## What is UTM?

UTM is a continuous trust meter, with separate positive and negative learning
rates and a ramp for repeated betrayals. Its basic update intuition is:

$$
T_{new} = T_{old} + \alpha (R - T_{old})
$$

The implementation also applies severity, betrayal history, and clipping.
Explore **The Model** in the interface or read the existing
[model explanation](dash/pages/04_UTM_Explained.md) for context. Trust updates are
separate from the Prisoner’s Dilemma payoffs used to score tournaments.

This is an academic research prototype, not production safety, financial, legal,
or operational advice. Do not submit confidential or sensitive information.

## Project layout

| Path | Purpose |
| --- | --- |
| `frontend/` | Static React + TypeScript research interface |
| `backend/` | Direct streaming Python HTTP API and simulation services |
| `utm/`, `strategies/`, `tournaments/` | Reusable model and tournament code |
| `config/presets.yaml` | Approved research personality presets |
| `scripts/dev.py`, `run_local.sh` | Local launcher |
| `dash/` | Optional legacy interface, local sweeps, model documentation |
| `infra/serverless.yaml`, `Dockerfile.lambda` | AWS deployment template and backend packaging |

## Development and verification

```bash
poetry run pytest -q
npm --prefix frontend test
npm --prefix frontend run build
```

Browser tests start fresh local servers on ports 18000 and 15173. Install the test browser once:

```bash
cd frontend
npx playwright install chromium
npm run test:browser
```

Maintainers can run the two development services separately if preferred:

```bash
# Terminal 1, repository root
poetry run python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000

# Terminal 2, repository root
npm --prefix frontend run dev
```

`npm --prefix frontend run build` creates static assets in `frontend/dist/`.
Vite proxies `/api/*` to the local Python service during development; this proxy
is not part of the production static build.

## Hosting and optional submissions

The target AWS deployment serves React from private S3 through CloudFront.
CloudFront signs requests to an IAM-protected Lambda Function URL; the same
response carries progress and final results. Each simulation has isolated
state, and Lambda scales independent requests within the configured concurrency
limit. There is no application database, cloud queue, or durable job service.

[Deployment and cutover instructions](docs/DEPLOYMENT.md) explain how to validate
before changing the production hostname. This branch does not deploy itself.
The previous ECS workflow is retained as a manual legacy workflow.

| Environment variable | Purpose |
| --- | --- |
| `MAX_RUN_SECONDS` | Maximum request duration; default 240, bounded to 840 |
| `LOCAL_CONCURRENCY` | Per-process local simultaneous runs; default 2 |
| `PRESETS_S3_URI` | Optional approved preset YAML in S3; default is the repository file |
| `SUBMIT_PREFIX` | Optional private S3 prefix for suggestions; disabled when unset |
| `GIT_SHA` | Build revision displayed in the interface |
| `ENABLE_SWEEP_UI` | Enable optional local research sweeps |

Normal local runs do not call AWS. Only the optional S3 variables above require
AWS credentials and matching permissions. Preset suggestions are private records
for review; submitted presets are not automatically published. Do not submit
personal, confidential, or sensitive information.

Hosted demo: **https://utm.ignitumsolutions.com**. The deployed interface can
lag this development branch; use its displayed build revision to identify it.

## Attribution, licensing, and citation

This project uses [Axelrod-Python](https://github.com/Axelrod-Python/Axelrod) for
strategies and tournament mechanics. Dependencies are declared in the Python
and frontend manifests and lockfiles.

Code is MIT-licensed; see [LICENSE](LICENSE) and [NOTICE](NOTICE). Documentation
in `docs/` and dashboard Markdown in `dash/pages/` are CC BY 4.0; see
[documentation license](docs/LICENSE-CC-BY.txt).

Carlisle (2025). *The Universal Trust Model.*
https://github.com/ignitum-solutions/utm-ipd

See [CITATION.cff](CITATION.cff) for machine-readable citation metadata.
