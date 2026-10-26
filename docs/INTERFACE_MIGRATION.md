# Moving to the React research interface

Status: unreleased, on `feat/serverless-react-migration`.

The project is moving its public interface from Streamlit to a static React
frontend and a streaming Python backend. This supports efficient on-demand
execution, isolated concurrent runs, live synchronization of progress, and
scalability within explicit limits. It does not replace the Python trust model
or require researchers to become AWS developers.

## If you only use the website

The tournament, Moran process, Trust Game, model guide, presets, charts, and
exports remain available in the new interface. Live parameter sweeps still run
locally. Start a simulation and keep the page open to receive its updates.
The run controls, progress, and results appear above the parameter panels.
Submitting a run collapses its parameters; use View parameters to inspect the
fixed inputs during execution, or Edit parameters to configure the next run.
Results can be hidden and reopened without discarding them. Save observations
using Download CSV or save the full output with Results + settings. Each run
includes its seed and exact parameters. The study-design sections describe the
measurements and modeling assumptions. There is no generated interpretation
of completed runs. Results include recorded provenance, scoring protocol,
software versions, and effective parameter values for reproducibility.

If you try to switch tools while a run is active, the interface asks whether
you want to leave. Staying keeps the connection. Leaving disconnects it and
loses access to that run's result. Refreshing, closing, or navigating away uses
the browser's own warning, whose wording cannot be customized and which is not
guaranteed on every browser or mobile lifecycle event. A warning never claims
that closing the page reliably terminates the hosted Lambda process.

There is no server-side run history or recovery after a disconnect. Start a new
run explicitly if needed; the browser does not automatically resubmit it.

## If you already cloned this repository

After checking out this branch or the future release containing it:

```bash
poetry install
npm --prefix frontend ci
./run_local.sh
```

Open http://127.0.0.1:5173. Python 3.13, Poetry 2.2+, and Node.js 22.12+ are
required. On Windows use `poetry run python scripts/dev.py`. AWS credentials and
Docker are not required. The launcher stops both services with Ctrl+C.

Previously, `run_local.sh` started Docker Compose. It now starts the React
interface and Python service together. The old launcher flags are no longer
used. For the optional previous Docker interface, run `docker compose up --build`
and use port 8501 instead.

## If you use Python scripts or sweeps

Continue importing `utm`, `strategies`, and `tournaments`, or use `main.py` as
before. Install optional tools with `poetry install --with research` to keep
using the local Streamlit dashboard and parameter sweeps. Sweeps are not moved
to the public backend. Larger Python experiments are independent of web limits.

Moran runs stop at fixation or the requested generation maximum. The Trust Game
exposes trust parameters and a reproducible seed. Its output includes investment
fraction and nonnegative-payoff fraction as separate measurements. Retain
software versions along with parameters when comparing results across releases.

## For maintainers

The migration does not require deleting the running site before local testing.
The new stack can be checked at its generated CloudFront address before the
existing hostname changes. Only retire dedicated old resources after verifying
the replacement and preserving presets/submissions. Shared AWS resources remain
outside the cleanup scope.

See [deployment instructions](DEPLOYMENT.md) for the hosting architecture and
cutover procedure. Source changes do not deploy the application automatically.
