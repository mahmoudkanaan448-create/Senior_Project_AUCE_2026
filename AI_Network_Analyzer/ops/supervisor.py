"""
Process supervisor – keeps API + Dashboard alive on a server.

Restarts crashed processes, periodic health checks, auto-heal on DB issues.
Usage:
  python -m ops.supervisor
  (or run_server.bat)
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import LOGS_DIR

LOGS_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [supervisor] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "supervisor.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("supervisor")

API_PORT = int(os.getenv("AINDR_API_PORT", "8000"))
DASH_PORT = int(os.getenv("AINDR_DASH_PORT", "8501"))
HEALTH_URL = os.getenv("AINDR_HEALTH_URL", f"http://127.0.0.1:{API_PORT}/api/v1/health")
CHECK_EVERY = int(os.getenv("AINDR_CHECK_SECONDS", "15"))
MAX_RESTARTS_WINDOW = 8
RESTART_WINDOW_SEC = 300

_python = os.getenv("AINDR_PYTHON", sys.executable)
_streamlit = os.getenv(
    "AINDR_STREAMLIT",
    str(Path(_python).with_name("streamlit.exe" if os.name == "nt" else "streamlit")),
)


class ManagedProc:
    def __init__(self, name: str, cmd: List[str], cwd: Path):
        self.name = name
        self.cmd = cmd
        self.cwd = cwd
        self.proc: Optional[subprocess.Popen] = None
        self.restarts: List[float] = []
        self.log_path = LOGS_DIR / f"{name}.out.log"

    def start(self) -> None:
        self.stop()
        logger.info("Starting %s: %s", self.name, " ".join(self.cmd))
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        out = open(self.log_path, "a", encoding="utf-8")
        self.proc = subprocess.Popen(
            self.cmd,
            cwd=str(self.cwd),
            stdout=out,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        logger.info("%s pid=%s", self.name, self.proc.pid)

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                if os.name == "nt":
                    self.proc.terminate()
                else:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            try:
                self.proc.wait(timeout=8)
            except Exception:
                pass
        self.proc = None

    def ensure(self) -> bool:
        """Return True if a restart happened."""
        if self.alive():
            return False
        now = time.time()
        self.restarts = [t for t in self.restarts if now - t < RESTART_WINDOW_SEC]
        if len(self.restarts) >= MAX_RESTARTS_WINDOW:
            logger.error("%s restart storm – cooling down 60s", self.name)
            time.sleep(60)
            self.restarts.clear()
        logger.warning("%s not running – restarting", self.name)
        self.start()
        self.restarts.append(now)
        return True


def _api_healthy() -> bool:
    try:
        with urlopen(HEALTH_URL, timeout=5) as resp:
            return 200 <= getattr(resp, "status", 200) < 300
    except Exception:
        return False


def run() -> None:
    logger.info("AI-NDR supervisor starting @ %s", datetime.utcnow().isoformat())
    try:
        from ops.health import try_auto_heal
        heal = try_auto_heal()
        logger.info("startup heal: %s", heal)
    except Exception as exc:
        logger.warning("startup heal failed: %s", exc)

    api = ManagedProc(
        "api",
        [_python, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(API_PORT)],
        ROOT,
    )
    dash = ManagedProc(
        "dashboard",
        [
            _streamlit, "run", str(ROOT / "dashboard" / "home.py"),
            "--server.port", str(DASH_PORT),
            "--server.address", "0.0.0.0",
            "--browser.gatherUsageStats", "false",
            "--server.headless", "true",
        ],
        ROOT,
    )

    api.start()
    time.sleep(3)
    dash.start()

    capture = None
    if os.getenv("AINDR_CAPTURE", "0") in ("1", "true", "True", "yes"):
        cap_cmd = [_python, "-m", "monitoring.capture_daemon", "--iface", os.getenv("AINDR_CAPTURE_IFACE", "auto")]
        if os.getenv("AINDR_CAPTURE_DETECT", "1") in ("1", "true", "True", "yes"):
            cap_cmd.append("--detect")
        capture = ManagedProc("capture", cap_cmd, ROOT)
        capture.start()

    stop = {"flag": False}

    def _sig(_s, _f):
        stop["flag"] = True

    try:
        signal.signal(signal.SIGINT, _sig)
        signal.signal(signal.SIGTERM, _sig)
    except Exception:
        pass

    fail_streak = 0
    while not stop["flag"]:
        try:
            api.ensure()
            dash.ensure()
            if capture is not None:
                capture.ensure()

            if api.alive() and not _api_healthy():
                fail_streak += 1
                logger.warning("API health check failed (%s)", fail_streak)
                if fail_streak >= 3:
                    logger.warning("Auto-heal + API restart")
                    try:
                        from ops.health import try_auto_heal
                        try_auto_heal()
                    except Exception:
                        pass
                    api.start()
                    fail_streak = 0
            else:
                fail_streak = 0

            try:
                from response.policy import expire_temp_blocks
                n = expire_temp_blocks()
                if n:
                    logger.info("expired %s timed blocks", n)
            except Exception:
                pass
            try:
                from reports.scheduler import maybe_run_scheduled
                maybe_run_scheduled()
            except Exception:
                pass
        except Exception as exc:
            logger.exception("supervisor loop error: %s", exc)
        time.sleep(CHECK_EVERY)

    logger.info("Supervisor shutting down...")
    if capture is not None:
        capture.stop()
    dash.stop()
    api.stop()


if __name__ == "__main__":
    run()
