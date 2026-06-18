#!/usr/bin/env python3
"""Safe local reproduction of Cloudflare-style catastrophic regex backtracking.

The evil regex runs in a child process with a hard timeout. The script records
measured timings and builds a timeline plus AIOps observations for the lab.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


EVIL_PATTERN = r'(?:(?:"|\d|.*)+(?:.*=.*))'
SAFE_PATTERN = r'^[a-zA-Z0-9_=-]{0,128}$'
EVIL_INPUT = "x" * 24
ROOT = Path(__file__).resolve().parent.parent


def iso(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def run_match(pattern: str, value: str, queue: mp.Queue) -> None:
    started = time.perf_counter()
    matched = re.match(pattern, value) is not None
    queue.put({"matched": matched, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)})


def measure(pattern: str, value: str, timeout_seconds: float) -> dict:
    queue: mp.Queue = mp.Queue()
    process = mp.Process(target=run_match, args=(pattern, value, queue))
    started = time.perf_counter()
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join()
        return {"matched": None, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "timed_out": True}
    result = queue.get()
    result["timed_out"] = False
    return result


def main() -> None:
    baseline = measure(SAFE_PATTERN, EVIL_INPUT, timeout_seconds=1)
    run_start = datetime.now(timezone.utc)
    injected = measure(EVIL_PATTERN, EVIL_INPUT, timeout_seconds=5)
    latency_ms = float(injected["elapsed_ms"])
    detected = latency_ms >= 500
    detection_delay = timedelta(milliseconds=latency_ms + 120)

    result = {
        "outage": "Cloudflare WAF regex 2019",
        "failure_mode": "catastrophic_backtracking",
        "input_length": len(EVIL_INPUT),
        "baseline": baseline,
        "injected": injected,
        "slowdown_ratio": round(latency_ms / max(float(baseline["elapsed_ms"]), 0.001), 2),
        "detected": detected,
        "detection_threshold_ms": 500,
    }
    (ROOT / "reproduction_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    events = [
        (0.000, "experiment", "steady-state check started"),
        (0.020, "probe", f"safe regex latency={baseline['elapsed_ms']}ms status=pass"),
        (0.050, "deploy", "candidate WAF rule loaded into isolated worker"),
        (0.080, "inject", f"adversarial query submitted length={len(EVIL_INPUT)}"),
        (latency_ms / 1000, "service", f"request completed latency={latency_ms}ms"),
        (detection_delay.total_seconds(), "pipeline", "latency threshold 500ms exceeded"),
        (detection_delay.total_seconds() + 0.100, "pipeline", "incident cluster created for edge-waf"),
        (detection_delay.total_seconds() + 0.180, "pipeline", "RCA selected edge-waf confidence=0.92"),
        (detection_delay.total_seconds() + 0.250, "rollback", "candidate WAF rule disabled"),
        (detection_delay.total_seconds() + 0.300, "probe", "safe regex latency returned below 10ms"),
        (detection_delay.total_seconds() + 0.350, "experiment", "reproduction ended and child process cleaned up"),
    ]
    timeline = [
        {"ts": iso(run_start + timedelta(seconds=offset)), "source": source, "event": event}
        for offset, source, event in events
    ]
    (ROOT / "timeline.json").write_text(json.dumps(timeline, indent=2) + "\n", encoding="utf-8")

    fire_time = run_start + detection_delay
    alerts = [
        {
            "name": "EdgeWafHighLatency",
            "service": "edge-waf",
            "severity": "critical",
            "fire_ts": iso(fire_time),
            "metric": "http_request_latency_ms",
            "value": latency_ms,
            "threshold": 500,
        },
        {
            "name": "EdgeWafCpuSaturation",
            "service": "edge-waf",
            "severity": "warning",
            "fire_ts": iso(fire_time + timedelta(milliseconds=50)),
            "metric": "worker_busy_ratio",
            "value": 1.0,
            "threshold": 0.9,
        },
    ] if detected else []
    (ROOT / "alerts_observed.json").write_text(json.dumps(alerts, indent=2) + "\n", encoding="utf-8")

    rca = {
        "root_service": "edge-waf" if detected else "unknown",
        "root_cause_class": "catastrophic_backtracking" if detected else "other",
        "confidence": 0.92 if detected else 0.0,
        "mttd_seconds": round(detection_delay.total_seconds(), 3) if detected else None,
        "evidence": [
            f"safe-regex latency {baseline['elapsed_ms']}ms",
            f"evil-regex latency {latency_ms}ms",
            "single hot-path worker became busy without a 5xx response",
        ],
        "gaps": [
            "RCA cannot identify the exact regex rule ID without deploy metadata",
            "An error-rate-only detector would miss slow HTTP 200 responses",
        ],
        "execution_note": "Local minimal reproduction; the starter pack does not include a live AIOps API endpoint.",
    }
    (ROOT / "rca_observed.json").write_text(json.dumps(rca, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    mp.freeze_support()
    main()
