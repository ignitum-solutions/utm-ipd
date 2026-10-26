"""Start the local API and frontend together. No AWS credentials required."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent


def main():
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("Install Node.js 22.12+ (including npm), then follow the README setup.")
    if not (ROOT / "frontend/node_modules").exists():
        raise SystemExit("First run: npm --prefix frontend ci")
    processes = []
    env = os.environ.copy()
    env.setdefault("MPLCONFIGDIR", str(ROOT / ".local-runtime/matplotlib"))
    env.setdefault("XDG_CACHE_HOME", str(ROOT / ".local-runtime/cache"))
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    process_options = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                       if os.name == "nt" else {"start_new_session": True})

    def terminate(p, *, force=False):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            try:
                os.killpg(p.pid, signal.SIGKILL if force else signal.SIGTERM)
            except ProcessLookupError:
                pass

    try:
        processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT, env=env, **process_options))
        processes.append(subprocess.Popen([npm, "run", "dev"], cwd=ROOT / "frontend", env=env, **process_options))
        print("\nUTM local research interface: http://127.0.0.1:5173\nAPI: http://127.0.0.1:8000/api/health\nPress Ctrl+C to stop both.\n", flush=True)
        while all(p.poll() is None for p in processes):
            time.sleep(.25)
        failed = next((p.returncode for p in processes if p.poll() is not None), 1)
        if failed:
            raise SystemExit(f"A local server exited ({failed}). Check the messages above; ports 8000 and 5173 must be available.")
    except KeyboardInterrupt:
        print("\nStopping local servers…", flush=True)
    finally:
        for p in processes:
            if p.poll() is None:
                terminate(p)
        for p in processes:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                terminate(p, force=True)
                p.wait()


if __name__ == "__main__":
    main()
