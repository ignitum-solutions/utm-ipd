from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

from backend.models import MoranRequest, Suggestion, TournamentRequest, TrustRequest
from backend.streaming import encode, stream_run

app = FastAPI(title="UTM research interface", docs_url=None, redoc_url=None, openapi_url=None)
RUN_SECONDS = min(840, max(1, int(os.getenv("MAX_RUN_SECONDS", "240"))))
CAPACITY = max(1, int(os.getenv("LOCAL_CONCURRENCY", "2")))
_active = 0  # Local per-process admission only; AWS reserved concurrency is separate.


@app.middleware("http")
async def small_requests(request: Request, call_next):
    # Bound actual bytes, not just a caller-provided Content-Length.
    if request.method == "POST":
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16_384:
                return PlainTextResponse("Request too large.", status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok", "version": os.getenv("GIT_SHA", "local")}


@app.get("/api/catalogue")
def catalogue():
    from backend.catalogue import catalogue as describe
    return {**describe(), "max_run_seconds": RUN_SECONDS}


@app.get("/api/explanation", response_class=PlainTextResponse)
def explanation():
    return (Path(__file__).resolve().parent.parent / "dash/pages/04_UTM_Explained.md").read_text(encoding="utf-8")


async def launch(kind, config, presets=None):
    global _active
    # This increment has no await and is atomic within the single ASGI loop.
    if _active >= CAPACITY:
        raise HTTPException(429, "All simulation slots are busy. Please try again shortly.", headers={"Retry-After": "5"})
    _active += 1
    released = False

    def release():
        global _active
        nonlocal released
        if not released:
            _active -= 1
            released = True

    class BoundedResponse(StreamingResponse):
        async def __call__(self, scope, receive, send):
            try:
                # Cover time blocked writing to a slow client as well as CPU
                # work. The generator's own deadline emits a normal error first.
                async with asyncio.timeout(RUN_SECONDS + 2):
                    await super().__call__(scope, receive, send)
            except TimeoutError:
                # Headers may already be committed; report a terminal event.
                try:
                    async with asyncio.timeout(1):
                        await send({"type": "http.response.body", "body": encode({"type": "error", "message": "The run exceeded the demo time limit."}), "more_body": False})
                except (TimeoutError, OSError):
                    pass
            finally:
                try:
                    await self.body_iterator.aclose()
                finally:
                    release()

    return BoundedResponse(
        stream_run(kind, config.model_dump(), presets, seconds=RUN_SECONDS, on_close=release),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store, no-transform"},
    )


@app.post("/api/run/tournament")
async def run_tournament(config: TournamentRequest):
    from backend.catalogue import load_presets, validate_selections
    presets = await asyncio.to_thread(load_presets)
    try:
        await asyncio.to_thread(validate_selections, config, presets)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return await launch("tournament", config, presets)


@app.post("/api/run/moran")
async def run_moran(config: MoranRequest):
    return await launch("moran", config)


@app.post("/api/run/trust")
async def run_trust(config: TrustRequest):
    return await launch("trust", config)


@app.post("/api/suggestions", status_code=201)
def suggest(config: Suggestion):
    prefix = os.getenv("SUBMIT_PREFIX", "")
    if not prefix:
        raise HTTPException(404, "Preset suggestions are not enabled for this deployment.")
    if not prefix.startswith("s3://") or "/" not in prefix[5:]:
        raise HTTPException(503, "Preset suggestions are temporarily unavailable.")
    import boto3
    bucket, folder = prefix[5:].split("/", 1)
    key = f"{folder.rstrip('/')}/{dt.datetime.now(dt.UTC):%Y%m%dT%H%M%SZ}_{uuid.uuid4().hex}.json"
    try:
        boto3.client("s3").put_object(Bucket=bucket, Key=key,
                                     Body=json.dumps(config.model_dump()).encode(), ContentType="application/json")
    except Exception as exc:
        raise HTTPException(503, "Your suggestion could not be saved. Please try later.") from exc
    return {"message": "Suggestion saved for review. Thank you."}
