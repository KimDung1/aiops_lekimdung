#!/usr/bin/env python3
"""Streaming anomaly pipeline for the AIOps W1 individual lab.

Run:
    python pipeline.py --host 0.0.0.0 --port 8000

Then start the generator:
    python stream_generator.py --birthday YYYY-MM-DD --target http://localhost:8000/ingest
"""

from __future__ import annotations

import argparse
import json
import time
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ALERTS_FILE = Path("alerts.jsonl")
WINDOW_SIZE = 12
CONFIRMATION_POINTS = 2
ALERT_COOLDOWN_SECONDS = 300


class DetectorState:
    def __init__(self) -> None:
        self.window: deque[dict[str, Any]] = deque(maxlen=WINDOW_SIZE)
        self.last_alert_at: dict[str, float] = {}

    def add(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        metrics = payload.get("metrics", {})
        logs = payload.get("logs", [])
        timestamp = payload.get("timestamp") or now_iso()

        point = {
            "timestamp": timestamp,
            "metrics": metrics,
            "logs": logs,
            "signals": classify_signals(metrics, logs),
        }
        self.window.append(point)

        alerts = []
        for fault_type in ("dependency_timeout", "traffic_spike", "memory_leak"):
            if self._confirmed(fault_type) and self._cooldown_expired(fault_type):
                alert = build_alert(timestamp, fault_type, metrics, logs)
                self.last_alert_at[fault_type] = time.time()
                alerts.append(alert)
        return alerts

    def _confirmed(self, fault_type: str) -> bool:
        recent = list(self.window)[-3:]
        return sum(1 for point in recent if point["signals"].get(fault_type)) >= CONFIRMATION_POINTS

    def _cooldown_expired(self, fault_type: str) -> bool:
        last = self.last_alert_at.get(fault_type, 0)
        return time.time() - last >= ALERT_COOLDOWN_SECONDS


STATE = DetectorState()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def number(metrics: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(metrics.get(key, default))
    except (TypeError, ValueError):
        return default


def classify_signals(metrics: dict[str, Any], logs: list[dict[str, Any]]) -> dict[str, bool]:
    memory_usage = number(metrics, "memory_usage_bytes")
    memory_limit = max(number(metrics, "memory_limit_bytes", 1), 1)
    memory_util = memory_usage / memory_limit
    gc_pause = number(metrics, "jvm_gc_pause_ms_avg")
    cpu = number(metrics, "cpu_usage_percent")
    rps = number(metrics, "http_requests_per_sec")
    latency = number(metrics, "http_p99_latency_ms")
    error_rate = number(metrics, "http_5xx_rate")
    queue_depth = number(metrics, "queue_depth")
    upstream_timeout = number(metrics, "upstream_timeout_rate")
    log_text = " ".join(str(log.get("message", "")).lower() for log in logs)

    dependency_timeout = (
        upstream_timeout >= 5
        or "upstream timeout" in log_text
        or "circuit breaker" in log_text
    ) and latency >= 180

    traffic_spike = (
        rps >= 300
        and queue_depth >= 40
        and latency >= 200
        and upstream_timeout < 5
    ) or ("queue depth high" in log_text and rps >= 250)

    memory_leak = (
        memory_util >= 0.60
        and gc_pause >= 45
    ) or (
        memory_util >= 0.75
        and cpu >= 55
    ) or "outofmemorywarning" in log_text

    return {
        "memory_leak": memory_leak,
        "traffic_spike": traffic_spike,
        "dependency_timeout": dependency_timeout,
    }


def build_alert(
    timestamp: str,
    fault_type: str,
    metrics: dict[str, Any],
    logs: list[dict[str, Any]],
) -> dict[str, str]:
    memory_usage = number(metrics, "memory_usage_bytes")
    memory_limit = max(number(metrics, "memory_limit_bytes", 1), 1)
    memory_util = memory_usage / memory_limit * 100
    gc_pause = number(metrics, "jvm_gc_pause_ms_avg")
    rps = number(metrics, "http_requests_per_sec")
    latency = number(metrics, "http_p99_latency_ms")
    error_rate = number(metrics, "http_5xx_rate")
    queue_depth = number(metrics, "queue_depth")
    upstream_timeout = number(metrics, "upstream_timeout_rate")
    fatal_or_error = any(str(log.get("level", "")).upper() in {"ERROR", "FATAL"} for log in logs)

    if fault_type == "memory_leak":
        severity = "critical" if memory_util >= 75 or gc_pause >= 100 or fatal_or_error else "warning"
        message = (
            f"Memory usage growing abnormally: utilization={memory_util:.1f}%, "
            f"gc_pause_avg={gc_pause:.1f}ms"
        )
    elif fault_type == "traffic_spike":
        severity = "critical" if queue_depth >= 100 or error_rate >= 10 else "warning"
        message = (
            f"Traffic spike detected: rps={rps:.1f}, queue_depth={queue_depth:.0f}, "
            f"p99_latency={latency:.1f}ms"
        )
    else:
        severity = "critical" if upstream_timeout >= 30 or error_rate >= 10 or fatal_or_error else "warning"
        message = (
            f"Dependency timeout detected: upstream_timeout_rate={upstream_timeout:.1f}%, "
            f"5xx_rate={error_rate:.1f}%, p99_latency={latency:.1f}ms"
        )

    return {
        "timestamp": timestamp,
        "type": fault_type,
        "severity": severity,
        "message": message,
    }


def write_alerts(alerts: list[dict[str, str]]) -> None:
    if not alerts:
        return
    with ALERTS_FILE.open("a", encoding="utf-8") as file:
        for alert in alerts:
            file.write(json.dumps(alert, ensure_ascii=False) + "\n")


class PipelineHandler(BaseHTTPRequestHandler):
    server_version = "AIOpsPipeline/1.0"

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(200, {"status": "ok", "window_size": len(STATE.window)})
            return
        self.send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/ingest":
            self.send_json(404, {"error": "not found"})
            return

        try:
            payload = self.read_json_body()
            validate_payload(payload)
            alerts = STATE.add(payload)
            write_alerts(alerts)
            self.send_json(200, {"status": "ok", "alerts": len(alerts)})
        except ValueError as exc:
            self.send_json(400, {"status": "error", "message": str(exc)})
        except Exception as exc:  # Keep the streaming endpoint alive during the lab.
            self.send_json(500, {"status": "error", "message": str(exc)})

    def read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("empty request body")
        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        return payload

    def send_json(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def validate_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload.get("metrics"), dict):
        raise ValueError("payload.metrics must be an object")
    if not isinstance(payload.get("logs", []), list):
        raise ValueError("payload.logs must be a list")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIOps streaming anomaly pipeline")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    parser.add_argument("--alerts-file", default="alerts.jsonl", help="Alert output file")
    return parser.parse_args()


def main() -> None:
    global ALERTS_FILE
    args = parse_args()
    ALERTS_FILE = Path(args.alerts_file)
    ALERTS_FILE.touch(exist_ok=True)

    server = ThreadingHTTPServer((args.host, args.port), PipelineHandler)
    print(f"[PIPELINE] Listening on http://{args.host}:{args.port}/ingest")
    print(f"[PIPELINE] Writing alerts to {ALERTS_FILE.resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[PIPELINE] Stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
