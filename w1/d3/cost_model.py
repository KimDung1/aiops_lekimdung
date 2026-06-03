from __future__ import annotations


TIERS = {
    "Small": {"services": 10, "log_gb_day": 50, "metric_events_sec": 100_000},
    "Medium": {"services": 100, "log_gb_day": 500, "metric_events_sec": 1_000_000},
    "Large": {"services": 1_000, "log_gb_day": 5_000, "metric_events_sec": 10_000_000},
}


def estimate_build_cost(log_gb_day: int, metric_events_sec: int) -> dict[str, float]:
    hot_log_storage = log_gb_day * 7 * 0.30
    cold_log_storage = log_gb_day * 365 * 0.023
    metric_storage = metric_events_sec / 100_000 * 200
    kafka = metric_events_sec / 100_000 * 250
    stream_compute = metric_events_sec / 100_000 * 120
    network = log_gb_day * 30 * 0.02

    return {
        "hot_log_storage": hot_log_storage,
        "cold_log_storage": cold_log_storage,
        "metric_storage": metric_storage,
        "kafka_transport": kafka,
        "stream_compute": stream_compute,
        "network": network,
    }


def estimate_buy_cost(log_gb_day: int, metric_events_sec: int, services: int) -> dict[str, float]:
    log_ingest = log_gb_day * 30 * 1.70
    infra_monitoring = services * 35
    custom_metrics = metric_events_sec / 100_000 * 900
    apm = services * 20

    return {
        "log_ingest": log_ingest,
        "infra_monitoring": infra_monitoring,
        "custom_metrics": custom_metrics,
        "apm": apm,
    }


def money(value: float) -> str:
    return f"${value:,.0f}"


def print_table() -> None:
    print("# W1-D3 Cost Model")
    print()
    print("| Tier | Services | Log/day | Metric eps | Build/month | Buy Datadog/month | Recommendation |")
    print("|---|---:|---:|---:|---:|---:|---|")

    for tier, params in TIERS.items():
        build = estimate_build_cost(params["log_gb_day"], params["metric_events_sec"])
        buy = estimate_buy_cost(
            params["log_gb_day"], params["metric_events_sec"], params["services"]
        )
        build_total = sum(build.values())
        buy_total = sum(buy.values())
        recommendation = "Buy" if params["services"] <= 100 else "Build / hybrid"
        print(
            f"| {tier} | {params['services']:,} | {params['log_gb_day']:,} GB | "
            f"{params['metric_events_sec']:,} | {money(build_total)} | "
            f"{money(buy_total)} | {recommendation} |"
        )

    print()
    print("## Build Breakdown")
    for tier, params in TIERS.items():
        build = estimate_build_cost(params["log_gb_day"], params["metric_events_sec"])
        print(f"\n### {tier}")
        for key, value in build.items():
            print(f"- {key}: {money(value)}")
        print(f"- total: {money(sum(build.values()))}")


if __name__ == "__main__":
    print_table()
