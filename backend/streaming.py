"""Request-scoped process isolation and NDJSON, without durable jobs.

Pipes avoid the /dev/shm semaphores unavailable on Lambda. Each local request
gets the same process isolation as a Lambda invocation. No work is detached
after its stream is closed. AWS may not propagate a browser disconnect, so the
wall-clock limit is authoritative even when the client leaves.
"""
from __future__ import annotations

import asyncio
import json
import logging
import multiprocessing as mp
import time
from contextlib import suppress

logger = logging.getLogger(__name__)


def encode(event: dict) -> bytes:
    return (json.dumps(event, allow_nan=False, ensure_ascii=False) + "\n").encode()


def worker(connection, kind: str, config: dict, presets: dict | None, seconds: float):
    started = time.monotonic()
    last_progress = 0.0

    def checkpoint():
        if time.monotonic() - started > seconds:
            raise TimeoutError("The demo run reached its time limit. Reduce the settings or run the experiment locally.")

    def emit(event):
        nonlocal last_progress
        now = time.monotonic()
        if event.get("percent") not in (None, 100) and now - last_progress < 0.25:
            return
        connection.send_bytes(encode(event))
        last_progress = now

    try:
        # Scientific libraries load only for the experiments that use them.
        # The HTTP loop can heartbeat while a worker initializes those libraries.
        if kind == "trust":
            from backend.models import TrustRequest
            from backend.trust_game import trust_game
            result = trust_game(TrustRequest(**config), emit, checkpoint)
        else:
            from backend.engine import simulate
            result = simulate(kind, config, emit, checkpoint, presets)
        result["metadata"]["execution_limits"] = {"wall_clock_seconds": seconds, "completion": "full requested run or explicit error; no partial score substitution"}
        checkpoint()
        connection.send_bytes(encode({"type": "result", "result": result}))
    except TimeoutError as exc:
        connection.send_bytes(encode({"type": "error", "message": str(exc)}))
    except Exception:
        logger.exception("Simulation failed")
        with suppress(BrokenPipeError, OSError):
            connection.send_bytes(encode({"type": "error", "message": "The simulation could not finish. Try fewer players or smaller settings."}))
    finally:
        connection.close()


async def stream_run(kind: str, config: dict, presets=None, *, seconds=240, heartbeat_seconds=5, on_close=None):
    context = mp.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    process = context.Process(target=worker, args=(send, kind, config, presets, seconds), daemon=True)
    start = time.monotonic()
    last_sent = start
    started = False
    try:
        process.start()
        started = True
        send.close()
        yield encode({"type": "started", "phase": "Preparing your simulation", "percent": None})
        while True:
            now = time.monotonic()
            if now - start > seconds:
                yield encode({"type": "error", "message": "The demo run reached its time limit. Reduce the settings or run locally."})
                break
            # Read in a thread: a large terminal result may not fit in the pipe.
            if receive.poll():
                try:
                    data = await asyncio.to_thread(receive.recv_bytes)
                except EOFError:
                    yield encode({"type": "error", "message": "The simulation stopped before returning a result."})
                    break
                yield data
                last_sent = now
                if json.loads(data)["type"] in {"result", "error"}:
                    break
            elif not process.is_alive():
                yield encode({"type": "error", "message": "The simulation stopped before returning a result."})
                break
            elif now - last_sent >= heartbeat_seconds:
                yield encode({"type": "heartbeat", "elapsed": round(now - start, 1)})
                last_sent = now
            else:
                await asyncio.sleep(0.05)
    finally:
        # Includes ASGI cancellation on a locally observed disconnect.
        if started:
            if process.is_alive():
                process.terminate()
            process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join(timeout=1)
            process.close()
        receive.close()
        send.close()
        if on_close:
            on_close()
