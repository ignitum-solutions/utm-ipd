# Universal Trust Model × Iterated Prisoner’s Dilemma

<p align="center">
  <img src="dash/static/IgnitumSolutions_RGB_Icon.png" width="120" alt="Ignitum logo">
</p>

[![License: MIT](https://img.shields.io/github/license/ignitum-solutions/utm-ipd)](LICENSE)
[![Build & Deploy](https://github.com/ignitum-solutions/utm-ipd/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/ignitum-solutions/utm-ipd/actions/workflows/deploy.yml)
[![Dockerfile](https://img.shields.io/badge/dockerfile-root%2FDockerfile-blue)](Dockerfile)

> Code in this repository is MIT-licensed. See **LICENSE** and **NOTICE** for attribution details.
> Documentation and dashboard Markdown in `docs/` and `dash/pages/*.md` are released under **CC BY 4.0** (see docs/LICENSE-CC-BY).

---

## What’s the Universal Trust Model?

UTM is a **five-parameter, continuous trust meter**:

$$
\boxed{T_{\text{new}} = T_{\text{old}} + \alpha \,(R - T_{\text{old}})}
$$

It **rises** when an interaction is favourable and **falls** (asymmetrically)
when it is harmful.
Because UTM is **domain-agnostic** and differentiable, it can power everything
from simple repeated games to large-scale multi-agent simulations.

**Want the math & intuition?**
See [`dash/pages/04_UTM_Explained.md`](dash/pages/04_UTM_Explained.md).

This public repository is an academic/research prototype for UTM and Iterated
Prisoner's Dilemma experiments. It is not production safety, financial, legal,
or operational advice, and it does not include confidential private or
commercial implementation details.

---

## Repo contents

| Path / file                          | Why it’s cool                                                                                    |
| ------------------------------------ | ------------------------------------------------------------------------------------------------ |
| `dash/`                              | **Streamlit playground** – live sliders for θ α⁺ α⁻ δ τ, lightweight demos, and local-only sweep tools. |
| `tournaments/`                       | Round-robin driver built on Axelrod-Python – live leaderboard with cooperation rates.            |
| `Dockerfile`                         | Single-step container build; CI tags every image with the git short-SHA.                         |
| `.github/workflows/build-deploy.yml` | GitHub Actions → ECR → ECS deployment pipeline.                                                  |

---

## Quick start (Docker, 30 s)

```bash
docker build -t utm-ipd .
docker run --rm -p 8501:8501 utm-ipd
# open http://localhost:8501
```

_(If you publish to ECR or GHCR, replace the first line with
`docker pull public.ecr.aws/…/utm-ipd:latest` and run the same command.)_

---

## Developer setup (Poetry)

```bash
git clone https://github.com/ignitum-solutions/utm-ipd.git
cd utm-ipd
poetry install
poetry run streamlit run dash/00_IPD_Tournament.py
```

### Optional env-vars

| Variable         | Purpose                                | Example                       |
| ---------------- | -------------------------------------- | ----------------------------- |
| `PRESETS_S3_URI` | Load classroom UTM presets from S3     | `s3://my-bucket/presets.yaml` |
| `SUBMIT_PREFIX`  | Allow users to upload new preset ideas | `s3://my-bucket/submissions/` |
| `GIT_SHA`        | (injected by CI) show build hash in UI | `1a2b3c4`                     |
| `ENABLE_SWEEP_UI` | Enable CPU-intensive sweep pages locally | `true` |

Sweep and scan tools are disabled by default in the hosted demo to protect the
shared VM. To run them locally after cloning:

```bash
ENABLE_SWEEP_UI=true poetry run streamlit run dash/pages/01_IPD_Mini_Sweep.py
```

Keep sweeps small. They run tournaments repeatedly and can consume substantial
CPU. The Streamlit sweep page enforces conservative runtime limits and allows
one sweep at a time in a single app process.

The optional reward-matrix sweep is IPD-scoped: it varies how cooperate/defect
outcomes are mapped into signed UTM event rewards for these academic
simulations.

---

## Live demo

The playground is running 24 / 7 at
▶ **<https://utm.ignitumsolutions.com>**

No install needed—open the link, tweak the sliders, and watch the
tournament & Moran dashboards update in real time.

If preset suggestions are enabled on a deployment, submitted names, handles,
parameters, and descriptions may be stored for review. Do not submit
confidential, personal, or sensitive information.

---

## Third-party attribution

This project uses [Axelrod-Python](https://github.com/Axelrod-Python/Axelrod)
for Iterated Prisoner's Dilemma strategies and tournament mechanics. The
dashboard is built with Streamlit and scientific Python packages declared in
`pyproject.toml`.

---

## Citation

> Carlisle (2025). _The Universal Trust Model._
> <https://github.com/ignitum-solutions/utm-ipd>

➡️ A full BibTeX / EndNote entry is available via the
[CITATION.cff](CITATION.cff) file or the “Cite this repository” button on
GitHub.

## Contributing

Pull-requests and issues welcome! Please run `pre-commit install`
and keep `pytest` green before opening a PR.

---

## License

Code is MIT-licensed. Attribution and citation are appreciated, but not an
extra legal condition of the MIT license. Documentation and dashboard Markdown
in `docs/` and `dash/pages/*.md` are CC BY 4.0.
