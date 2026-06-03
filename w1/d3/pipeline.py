from __future__ import annotations

import csv
import json
import math
import queue
import random
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, pstdev


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "realKnownCause" / "machine_temperature_system_failure.csv"
OUTPUT_PATH = BASE_DIR / "features.json"
WINDOW_SIZE = 12  # 12 rows * 5 minutes = 1 hour rolling window


def ensure_input_csv(path: Path) -> None:
    """Create a deterministic NAB-like input file when the real dataset is absent."""
    if path.exists():
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)
    start = datetime(2013, 12, 2, 21, 15)
    rows = []

    for i in range(22_695):
        ts = start + timedelta(minutes=5 * i)
        daily_cycle = 8.0 * math.sin((i % 288) / 288 * 2 * math.pi)
        weekly_cycle = 2.0 * math.sin((i % 2016) / 2016 * 2 * math.pi)
        noise = rng.gauss(0, 1.2)
        value = 70.0 + daily_cycle + weekly_cycle + noise

        if 17_500 <= i <= 17_620:
            value += 25.0 + rng.gauss(0, 2.0)
        if 20_200 <= i <= 20_260:
            value -= 18.0 + rng.gauss(0, 1.5)

        rows.append({"timestamp": ts.isoformat(sep=" "), "value": round(value, 3)})

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["timestamp", "value"])
        writer.writeheader()
        writer.writerows(rows)


def producer(path: Path, stream: queue.Queue[dict]) -> int:
    count = 0
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            stream.put(
                {
                    "timestamp": row["timestamp"],
                    "metric": "machine_temperature",
                    "value": float(row["value"]),
                    "source": "NAB.realKnownCause.machine_temperature_system_failure",
                }
            )
            count += 1
    stream.put({"type": "EOF"})
    return count


def consume_features(stream: queue.Queue[dict]) -> list[dict]:
    values: deque[float] = deque(maxlen=WINDOW_SIZE)
    previous_value: float | None = None
    features = []

    while True:
        event = stream.get()
        if event.get("type") == "EOF":
            break

        value = event["value"]
        values.append(value)
        rolling_mean = mean(values)
        rolling_std = pstdev(values) if len(values) > 1 else 0.0
        rate_of_change = 0.0 if previous_value is None else value - previous_value
        z_score = 0.0 if rolling_std == 0 else (value - rolling_mean) / rolling_std

        features.append(
            {
                "timestamp": event["timestamp"],
                "metric": event["metric"],
                "value": round(value, 4),
                "rolling_mean_1h": round(rolling_mean, 4),
                "rolling_std_1h": round(rolling_std, 4),
                "rate_of_change": round(rate_of_change, 4),
                "z_score_1h": round(z_score, 4),
                "is_anomaly_signal": abs(z_score) >= 3.0,
            }
        )
        previous_value = value

    return features


def main() -> None:
    ensure_input_csv(DATA_PATH)
    stream: queue.Queue[dict] = queue.Queue()

    produced = producer(DATA_PATH, stream)
    features = consume_features(stream)

    with OUTPUT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(features, fh, indent=2)

    anomaly_count = sum(1 for item in features if item["is_anomaly_signal"])
    print("AIOps W1-D3 Mock Streaming Pipeline")
    print(f"Input rows emitted     : {produced:,}")
    print(f"Feature rows generated : {len(features):,}")
    print(f"Anomaly signals        : {anomaly_count:,}")
    print(f"Output                 : {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
