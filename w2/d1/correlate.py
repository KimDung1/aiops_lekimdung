"""Alert correlation pipeline for W2-D1.

The implementation combines:
- fingerprint dedup metadata
- session windows by timestamp gap
- topology-aware grouping by service graph distance
- explicit singleton handling for alerts marked as noise/unrelated
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any


SEVERITY_RANK = {"info": 0, "warn": 1, "crit": 2}
NOISE_WORDS = ("unrelated", "noise", "independent")


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_alerts(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def load_services(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def fingerprint(alert: dict[str, Any]) -> str:
    return f"{alert['service']}|{alert['metric']}|{alert['severity']}"


def is_noise(alert: dict[str, Any]) -> bool:
    note = str(alert.get("labels", {}).get("note", "")).lower()
    return any(word in note for word in NOISE_WORDS)


def build_graph(services_doc: dict[str, Any]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for service in services_doc.get("services", []):
        graph[service["name"]]
    for store in services_doc.get("stores", []):
        graph[store["name"]]
    for edge in services_doc.get("edges", []):
        src = edge["from"]
        dst = edge["to"]
        graph[src].add(dst)
        graph[dst].add(src)
        if edge.get("via"):
            via = edge["via"]
            graph[src].add(via)
            graph[via].add(src)
            graph[via].add(dst)
            graph[dst].add(via)
    return graph


def shortest_hop(graph: dict[str, set[str]], start: str, end: str) -> int | None:
    if start == end:
        return 0
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    seen = {start}
    while queue:
        node, dist = queue.popleft()
        for neighbor in graph.get(node, set()):
            if neighbor == end:
                return dist + 1
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, dist + 1))
    return None


def session_groups(alerts: list[dict[str, Any]], gap_sec: int = 120) -> list[list[dict[str, Any]]]:
    if not alerts:
        return []
    sorted_alerts = sorted(alerts, key=lambda alert: parse_ts(alert["ts"]))
    groups = [[sorted_alerts[0]]]
    for alert in sorted_alerts[1:]:
        gap = (parse_ts(alert["ts"]) - parse_ts(groups[-1][-1]["ts"])).total_seconds()
        if gap <= gap_sec:
            groups[-1].append(alert)
        else:
            groups.append([alert])
    return groups


def topology_group(
    alerts: list[dict[str, Any]],
    graph: dict[str, set[str]],
    max_hop: int = 1,
) -> list[list[dict[str, Any]]]:
    if not alerts:
        return []

    clean_alerts = [alert for alert in alerts if not is_noise(alert)]
    singleton_alerts = [[alert] for alert in alerts if is_noise(alert)]
    if not clean_alerts:
        return singleton_alerts

    services = sorted({alert["service"] for alert in clean_alerts})
    parent = {service: service for service in services}

    def find(service: str) -> str:
        while parent[service] != service:
            parent[service] = parent[parent[service]]
            service = parent[service]
        return service

    def union(left: str, right: str) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for index, left in enumerate(services):
        for right in services[index + 1 :]:
            hop = shortest_hop(graph, left, right)
            if hop is not None and hop <= max_hop:
                union(left, right)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for alert in clean_alerts:
        grouped[find(alert["service"])].append(alert)
    return list(grouped.values()) + singleton_alerts


def max_severity(alerts: list[dict[str, Any]]) -> str:
    return max((alert["severity"] for alert in alerts), key=lambda item: SEVERITY_RANK.get(item, -1))


def summarize_cluster(cluster_id: str, alerts: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(alerts, key=lambda alert: parse_ts(alert["ts"]))
    return {
        "cluster_id": cluster_id,
        "alert_count": len(ordered),
        "services": sorted({alert["service"] for alert in ordered}),
        "time_range": [ordered[0]["ts"], ordered[-1]["ts"]],
        "max_severity": max_severity(ordered),
        "fingerprints": sorted({fingerprint(alert) for alert in ordered}),
        "alert_ids": [alert["id"] for alert in ordered],
    }


def correlate(
    alerts: list[dict[str, Any]],
    services_doc: dict[str, Any],
    gap_sec: int = 120,
    max_hop: int = 1,
) -> dict[str, Any]:
    graph = build_graph(services_doc)
    clusters = []
    for session_index, session in enumerate(session_groups(alerts, gap_sec=gap_sec), start=1):
        groups = topology_group(session, graph, max_hop=max_hop)
        groups = sorted(groups, key=lambda group: parse_ts(min(alert["ts"] for alert in group)))
        for group_index, group in enumerate(groups):
            cluster_id = f"c-{session_index:03d}-{group_index:03d}"
            clusters.append(summarize_cluster(cluster_id, group))

    return {
        "input_alerts": len(alerts),
        "output_clusters": len(clusters),
        "reduction_ratio": round(1 - (len(clusters) / len(alerts)), 2) if alerts else 0,
        "parameters": {
            "gap_sec": gap_sec,
            "max_hop": max_hop,
            "noise_words": list(NOISE_WORDS),
        },
        "clusters": clusters,
    }


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    alerts = load_alerts(base_dir / "dataset" / "alerts_sample.jsonl")
    services_doc = load_services(base_dir / "dataset" / "services.json")
    summary = correlate(alerts, services_doc, gap_sec=120, max_hop=1)
    output_path = base_dir / "results" / "cluster_summary.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
