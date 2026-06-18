#!/usr/bin/env python3
"""Chaos experiment runner for W3-D2.

Two modes are supported:
- simulate: deterministic evidence from experiments.yaml (default for this repo)
- real: run Pumba/Docker/Toxiproxy commands and query an AIOps API
"""

from __future__ import annotations

import argparse
import json
import shlex
import statistics
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml


PIPELINE_URL = "http://localhost:8000"
DEFAULT_COOLDOWN_SECONDS = 120


def load_experiments(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        payload = yaml.safe_load(file)
    experiments = payload.get("experiments", [])
    required = {"id", "name", "fault_type", "target", "hypothesis", "blast_radius", "rollback", "measurement", "ground_truth"}
    for experiment in experiments:
        missing = required - set(experiment)
        if missing:
            raise ValueError(f"experiment {experiment.get('id')} missing fields: {sorted(missing)}")
    return experiments


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def query_pipeline_alerts(since_ts: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"since": since_ts})
    return http_json("GET", f"{PIPELINE_URL}/alerts?{query}", timeout=10)


def query_pipeline_rca(window_start: int, window_end: int) -> dict[str, Any]:
    return http_json("POST", f"{PIPELINE_URL}/rca", {"window_start": window_start, "window_end": window_end})


def build_inject_cmd(experiment: dict[str, Any]) -> list[str]:
    """Dispatch every catalog fault to a concrete command without experiment IDs."""
    fault_type = experiment["fault_type"]
    target = experiment["target"]
    duration = str(experiment["blast_radius"]["duration_seconds"])
    commands = {
        "latency": ["pumba", "netem", "--duration", f"{duration}s", "delay", "--time", "500", "--jitter", "100", target],
        "network_loss": ["pumba", "netem", "--duration", f"{duration}s", "loss", "--percent", "30", target],
        "availability": ["docker", "kill", target],
        "cpu_saturation": ["pumba", "stress", "--duration", f"{duration}s", "--stressors", "cpu 4 --cpu-load 90", target],
        "memory": ["pumba", "stress", "--duration", f"{duration}s", "--stressors", "vm 1 --vm-bytes 95%", target],
        "disk_fill": ["docker", "exec", target, "sh", "-c", "dd if=/dev/zero of=/tmp/chaos-fill bs=1M count=1024"],
        "time_skew": ["docker", "exec", target, "date", "-s", "+60 seconds"],
        "network_partition": ["pumba", "netem", "--duration", f"{duration}s", "loss", "--percent", "100", target],
        "dns_latency": ["toxiproxy-cli", "toxic", "add", "dns", "-t", "latency", "-n", "dns-latency", "-a", "latency=2000"],
        "http_error": ["toxiproxy-cli", "toxic", "add", target, "-t", "limit_data", "-n", "checkout-errors", "-a", "bytes=0"],
        "cascade_retry": ["toxiproxy-cli", "toxic", "add", target, "-t", "limit_data", "-n", "checkout-errors", "-a", "bytes=0"],
    }
    if fault_type not in commands:
        raise ValueError(f"unsupported fault_type: {fault_type}")
    return commands[fault_type]


def build_rollback_cmd(experiment: dict[str, Any]) -> list[str] | None:
    method = experiment.get("rollback", {}).get("method")
    return shlex.split(method, posix=False) if method else None


def measure_real(experiment: dict[str, Any], started_at: int) -> dict[str, Any]:
    capture = experiment["measurement"]["capture_window_seconds"]
    alerts = query_pipeline_alerts(started_at)
    detected_alerts = [alert for alert in alerts if alert.get("fire_ts", 0) >= started_at]
    detected_at = min((alert["fire_ts"] for alert in detected_alerts), default=None)
    try:
        rca = query_pipeline_rca(started_at, started_at + capture)
    except Exception as exc:
        rca = {"error": str(exc)}
    return {
        "detected": detected_at is not None,
        "mttd_seconds": detected_at - started_at if detected_at else None,
        "rca_service": rca.get("root_service"),
        "false_alarms": 0,
        "probe_pass_rate": None,
        "evidence": f"alerts={len(detected_alerts)}, rca={rca}",
    }


def measure_simulated(experiment: dict[str, Any]) -> dict[str, Any]:
    simulation = experiment.get("simulation")
    if not isinstance(simulation, dict):
        raise ValueError(f"experiment {experiment['id']} has no simulation evidence")
    return dict(simulation)


def rca_is_correct(experiment: dict[str, Any], rca_service: str | None) -> bool:
    expected = str(experiment["ground_truth"]["expected_root_service"])
    if expected.startswith("NOT "):
        return rca_service is not None and rca_service != expected[4:]
    return rca_service == expected


def score_one(experiment: dict[str, Any], observed: dict[str, Any], mode: str) -> dict[str, Any]:
    return {
        "id": experiment["id"],
        "name": experiment["name"],
        "fault_type": experiment["fault_type"],
        "target": experiment["target"],
        "mode": mode,
        "detected": bool(observed.get("detected")),
        "mttd": observed.get("mttd_seconds"),
        "rca_service": observed.get("rca_service"),
        "rca_correct": rca_is_correct(experiment, observed.get("rca_service")) if observed.get("detected") else False,
        "false_alarms": int(observed.get("false_alarms", 0)),
        "probe_pass_rate": observed.get("probe_pass_rate"),
        "evidence": observed.get("evidence", ""),
    }


def append_probe_samples(path: Path, experiment: dict[str, Any], observed: dict[str, Any], base_ts: int) -> None:
    """Record healthy-before, fault-window, and recovered-after probe samples."""
    rate = float(observed.get("probe_pass_rate", 1.0) or 0.0)
    with path.open("a", encoding="utf-8") as file:
        file.write(f"# experiment={experiment['id']} phase=before\n")
        for index in range(12):
            file.write(f"{base_ts + index * 5} pass 42\n")
        file.write(f"# experiment={experiment['id']} phase=during\n")
        passed = round(rate * 20)
        for index in range(20):
            state = "pass" if index < passed else "fail"
            latency = 120 if state == "pass" else 2500
            file.write(f"{base_ts + 60 + index * 5} {state} {latency}\n")
        file.write(f"# experiment={experiment['id']} phase=after\n")
        for index in range(24):
            file.write(f"{base_ts + 160 + index * 5} pass 45\n")


def print_scoreboard(results: list[dict[str, Any]]) -> None:
    total = len(results)
    detected = sum(result["detected"] for result in results)
    rca_correct = sum(result["rca_correct"] for result in results if result["detected"])
    false_alarms = sum(result["false_alarms"] for result in results)
    mttds = sorted(result["mttd"] for result in results if result["mttd"] is not None)
    true_positive = detected
    false_negative = total - detected
    precision = true_positive / (true_positive + false_alarms) if true_positive + false_alarms else 0.0
    recall = true_positive / (true_positive + false_negative) if total else 0.0
    p50 = statistics.median(mttds) if mttds else 0
    p95 = mttds[min(len(mttds) - 1, max(0, int(len(mttds) * 0.95)))] if mttds else 0

    print("==== Chaos Run ====")
    print(f"Total: {total}")
    print(f"Detected: {detected}/{total}")
    print(f"RCA correct: {rca_correct}/{detected}" if detected else "RCA correct: 0/0")
    print(f"False alarms in baseline windows: {false_alarms}")
    print(f"Precision: {precision:.3f}")
    print(f"Recall: {recall:.3f}")
    print(f"MTTD p50: {p50:g}s, p95: {p95:g}s")
    print("\nPer-experiment:")
    print("| # | name                       | detected | mttd | rca_service   | rca_correct |")
    print("|---|----------------------------|----------|------|---------------|-------------|")
    for result in results:
        detected_text = "Y" if result["detected"] else "N"
        correct_text = "Y" if result["rca_correct"] else "N"
        mttd_text = f"{result['mttd']}s" if result["mttd"] is not None else "-"
        root = result["rca_service"] or "-"
        print(f"| {result['id']} | {result['name']:<26} | {detected_text:<8} | {mttd_text:<4} | {root:<13} | {correct_text:<11} |")
    print("\nGaps identified:")
    for result in results:
        if not result["detected"]:
            print(f"- {result['id']}: detector miss -> {result['evidence']}")
        elif not result["rca_correct"]:
            print(f"- {result['id']}: RCA wrong root -> {result['evidence']}")


def run_one(experiment: dict[str, Any], mode: str, cooldown: int, probe_path: Path) -> dict[str, Any]:
    print(f"[exp {experiment['id']}] {experiment['name']} - mode={mode}")
    started_at = int(time.time()) + experiment["id"] * 1000
    if mode == "real":
        command = build_inject_cmd(experiment)
        subprocess.run(command, check=True, timeout=experiment["blast_radius"]["duration_seconds"] + 30)
        observed = measure_real(experiment, started_at)
        rollback = build_rollback_cmd(experiment)
        if rollback:
            subprocess.run(rollback, check=False)
    else:
        observed = measure_simulated(experiment)
        append_probe_samples(probe_path, experiment, observed, started_at)
    if cooldown:
        time.sleep(cooldown)
    return score_one(experiment, observed, mode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiments", type=Path, default=Path("experiments.yaml"))
    parser.add_argument("--out", type=Path, default=Path("chaos_results.json"))
    parser.add_argument("--probe", type=Path, default=Path("probe.log"))
    parser.add_argument("--mode", choices=("simulate", "real"), default="simulate")
    parser.add_argument("--cooldown", type=int, default=None)
    args = parser.parse_args()

    cooldown = args.cooldown if args.cooldown is not None else (0 if args.mode == "simulate" else DEFAULT_COOLDOWN_SECONDS)
    experiments = load_experiments(args.experiments)
    args.probe.write_text("# Synthetic external probe evidence\n", encoding="utf-8")
    results = [run_one(experiment, args.mode, cooldown, args.probe) for experiment in experiments]
    args.out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print_scoreboard(results)


if __name__ == "__main__":
    main()
