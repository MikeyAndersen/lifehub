"""LifeHub GPU boot agent.

Runs briefly on the gaming PC (Windows, AMD RX 7900 XTX) — normally started
by Task Scheduler at log-on — and drains the server's review queue through
the strong Ollama model, then unloads the model and exits.

Flow:
  1. Wait until GPU utilisation is below GPU_START_THRESHOLD (skippable
     with --now; fail-open if the counter can't be read).
  2. Make sure Ollama is running (start it with OLLAMA_HOST=0.0.0.0 if not).
  3. POST {LIFEHUB_SERVER_URL}/api/review/drain in a loop until the server
     reports processed == 0, or TIMEBOX_MINUTES have passed.
  4. Ask Ollama to unload the model (keep_alive 0) and exit. No periodic
     re-runs — messages arriving later are caught at the next boot.

Stdlib only — no pip installs needed on the PC.

Usage:
  python gpu_agent.py                 # boot default: 30% check, 10 min box
  python gpu_agent.py --now           # skip the GPU-idle wait
  python gpu_agent.py --minutes 25    # longer timebox
  python gpu_agent.py --once          # exactly one drain round, then exit
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
log = logging.getLogger("gpu_agent")

IDLE_CHECK_INTERVAL_S = 15   # how often to re-measure a busy GPU
IDLE_REQUIRED_S = 120        # busy GPU must stay idle this long before we start
DRAIN_TIMEOUT_S = 600        # one drain call parses up to 10 messages on the LLM
MAX_CONSECUTIVE_ERRORS = 3


def _load_env() -> None:
    """Fill os.environ from agent/.env (existing variables win)."""
    env_file = HERE / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _cfg() -> dict:
    return {
        "server_url": os.environ.get("LIFEHUB_SERVER_URL", "").rstrip("/"),
        "token": os.environ.get("REVIEW_DRAIN_TOKEN", ""),
        "threshold": float(os.environ.get("GPU_START_THRESHOLD", "30")),
        "timebox_min": float(os.environ.get("TIMEBOX_MINUTES", "10")),
        "model": os.environ.get("OLLAMA_MODEL", ""),
        "ollama_url": os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
    }


# ── GPU measurement (isolated on purpose: swap this on a hardware change) ──


def gpu_utilization() -> float | None:
    """Total GPU engine utilisation in percent via Windows perf counters.

    The RX 7900 XTX has no nvidia-smi/rocm-smi on Windows, so we sum the
    "GPU Engine" utilisation counters instead. Returns None if the counter
    is unavailable — callers must fail open (measuring is a courtesy).
    """
    try:
        out = subprocess.run(
            ["typeperf", r"\GPU Engine(*)\Utilization Percentage", "-sc", "1"],
            capture_output=True, text=True, timeout=30,
        ).stdout
        # Last non-empty CSV row: "timestamp","v1","v2",...
        rows = [r for r in out.splitlines() if r.startswith('"')]
        values = [float(v.strip('"')) for v in rows[-1].split(",")[1:] if v.strip('"')]
        return sum(values)
    except Exception:
        return None


def wait_until_gpu_idle(threshold: float) -> None:
    """Block until the GPU has been below `threshold` % long enough to not
    disturb whatever is running. An immediately idle GPU starts at once."""
    usage = gpu_utilization()
    if usage is None:
        log.warning("GPU counter unavailable — continuing anyway (fail-open)")
        return
    if usage < threshold:
        log.info("GPU at %.0f%% (< %.0f%%) — starting", usage, threshold)
        return

    log.info("GPU busy at %.0f%% — waiting until below %.0f%% for %ds",
             usage, threshold, IDLE_REQUIRED_S)
    idle_since: float | None = None
    while True:
        time.sleep(IDLE_CHECK_INTERVAL_S)
        usage = gpu_utilization()
        if usage is None:
            log.warning("GPU counter went away — continuing (fail-open)")
            return
        if usage >= threshold:
            idle_since = None
            continue
        idle_since = idle_since or time.monotonic()
        if time.monotonic() - idle_since >= IDLE_REQUIRED_S:
            log.info("GPU idle long enough (now %.0f%%) — starting", usage)
            return


# ── Ollama ─────────────────────────────────────────────────────────


def _http_json(url: str, payload: dict | None = None, headers: dict | None = None,
               timeout: float = 10) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json",
                                          **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode() or "{}")


def ensure_ollama(cfg: dict) -> bool:
    try:
        _http_json(f"{cfg['ollama_url']}/api/tags", timeout=3)
        return True
    except OSError:
        pass

    log.info("Ollama not responding — starting `ollama serve` (OLLAMA_HOST=0.0.0.0)")
    env = {**os.environ, "OLLAMA_HOST": "0.0.0.0"}
    try:
        subprocess.Popen(["ollama", "serve"], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.DETACHED_PROCESS
                         | subprocess.CREATE_NEW_PROCESS_GROUP)
    except FileNotFoundError:
        log.error("`ollama` not found on PATH — install Ollama or start it manually")
        return False

    for _ in range(30):
        time.sleep(2)
        try:
            _http_json(f"{cfg['ollama_url']}/api/tags", timeout=3)
            return True
        except OSError:
            continue
    log.error("Ollama did not come up within 60s")
    return False


def unload_model(cfg: dict) -> None:
    """Free the VRAM immediately; a failure here is harmless (keep_alive
    on the server's calls already expires the model on its own)."""
    if not cfg["model"]:
        return
    try:
        _http_json(f"{cfg['ollama_url']}/api/generate",
                   {"model": cfg["model"], "keep_alive": 0}, timeout=30)
        log.info("Asked Ollama to unload %s", cfg["model"])
    except OSError as exc:
        log.warning("Could not unload model: %s", exc)


# ── Drain loop ─────────────────────────────────────────────────────


def drain_once(cfg: dict) -> dict | None:
    try:
        return _http_json(f"{cfg['server_url']}/api/review/drain",
                          payload={},
                          headers={"Authorization": f"Bearer {cfg['token']}"},
                          timeout=DRAIN_TIMEOUT_S)
    except urllib.error.HTTPError as exc:
        log.error("Server answered %s — check REVIEW_DRAIN_TOKEN / URL", exc.code)
        return None
    except OSError as exc:
        log.error("Could not reach server: %s", exc)
        return None


def drain_until_empty(cfg: dict, deadline: float) -> None:
    total_processed = total_corrected = errors = 0
    while time.monotonic() < deadline:
        result = drain_once(cfg)
        if result is None:
            errors += 1
            if errors >= MAX_CONSECUTIVE_ERRORS:
                log.error("Giving up after %d consecutive errors", errors)
                break
            time.sleep(10)
            continue
        errors = 0
        if result.get("online") is False:
            # Server can't reach THIS PC's Ollama: usually OLLAMA_HOST not
            # 0.0.0.0, a firewall rule, or Ollama still warming up.
            log.warning("Server reports the strong Ollama unreachable — retrying; "
                        "check OLLAMA_HOST=0.0.0.0 and the firewall if it persists")
            time.sleep(20)
            continue
        total_processed += result.get("processed", 0)
        total_corrected += result.get("corrected", 0)
        if result.get("processed", 0) == 0:
            log.info("Queue empty — done (processed %d, corrected %d this run)",
                     total_processed, total_corrected)
            return
        log.info("Batch done: %s (running total %d/%d)",
                 result, total_processed, total_corrected)
    else:
        log.info("Timebox reached — exiting (processed %d, corrected %d); "
                 "the rest is caught next boot", total_processed, total_corrected)


def main() -> int:
    ap = argparse.ArgumentParser(description="Drain LifeHub's review queue "
                                             "through the local strong model.")
    ap.add_argument("--minutes", type=float, default=None,
                    help="timebox in minutes (default: TIMEBOX_MINUTES, 10)")
    ap.add_argument("--now", action="store_true",
                    help="skip the GPU-idle check and start immediately")
    ap.add_argument("--once", action="store_true",
                    help="run exactly one drain round, then exit")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(HERE / "agent.log", encoding="utf-8")],
    )

    _load_env()
    cfg = _cfg()
    if not cfg["server_url"] or not cfg["token"]:
        log.error("LIFEHUB_SERVER_URL and REVIEW_DRAIN_TOKEN must be set "
                  "(agent/.env — see .env.example)")
        return 2

    if not args.now:
        wait_until_gpu_idle(cfg["threshold"])
    if not ensure_ollama(cfg):
        return 1

    try:
        if args.once:
            log.info("Single drain round: %s", drain_once(cfg))
        else:
            minutes = args.minutes if args.minutes is not None else cfg["timebox_min"]
            drain_until_empty(cfg, time.monotonic() + minutes * 60)
    finally:
        unload_model(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
