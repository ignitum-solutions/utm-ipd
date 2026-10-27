"""Serve build-generated strategy names without loading the simulation engine."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import get_args

import yaml

from backend.models import TournamentRequest, Variant

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = Path(os.getenv("UTM_CATALOGUE_PATH", str(ROOT / "config/catalogue.json")))


def live_registry() -> dict:
    # Local checkouts use the installed library; container builds save this data.
    from backend.engine import REGISTRY, STRATEGIES
    from dash.opponents import extra_opponent_options
    return {"variants": list(REGISTRY), "opponents": sorted(STRATEGIES),
            "extra_opponents": extra_opponent_options()}


def strategy_registry() -> dict:
    if REGISTRY_PATH.is_file():
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return live_registry()


def load_presets() -> dict:
    uri = os.getenv("PRESETS_S3_URI", str(ROOT / "config/presets.yaml"))
    if uri.startswith("s3://"):
        import boto3
        bucket, key = uri[5:].split("/", 1)
        source = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    else:
        source = Path(uri).read_text(encoding="utf-8")
    return yaml.safe_load(source) or {}


def catalogue() -> dict:
    registry = strategy_registry()
    return {**registry, "presets": load_presets(),
            "submissions_enabled": bool(os.getenv("SUBMIT_PREFIX")),
            "version": os.getenv("GIT_SHA", "local")}


def validate_selections(cfg: TournamentRequest, presets: dict) -> None:
    registry = strategy_registry()
    if any(name not in registry["opponents"] for name in cfg.opponents):
        raise ValueError("Choose opponents from the approved strategy list.")
    if any(name not in presets for name in cfg.presets):
        raise ValueError("Choose an existing parameter preset.")
    if cfg.extra_opponent not in registry["extra_opponents"]:
        raise ValueError("Choose an approved extra opponent.")


def write_registry(path: Path) -> None:
    registry = live_registry()
    if set(registry["variants"]) != set(get_args(Variant)):
        raise ValueError("The strategy registry and request variants differ.")
    path.write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", type=Path, required=True)
    write_registry(parser.parse_args().write)
