"""Production-style serving API for W2-D3.

Run locally after installing requirements:
    uvicorn serve:app --host 0.0.0.0 --port 8000 --workers 1
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field


APP_VERSION = "w2-d3-1.0.0"
GAP_SEC = int(os.getenv("AIOPS_GAP_SEC", "120"))
MAX_HOP = int(os.getenv("AIOPS_MAX_HOP", "1"))
RCA_METHOD = "graph+retrieval"
USE_LLM = os.getenv("AIOPS_USE_LLM", "false").lower() == "true"

BASE_DIR = Path(__file__).resolve().parent
W2_DIR = BASE_DIR.parent
D1_DIR = W2_DIR / "d1"
D2_DIR = W2_DIR / "d2"
for path in (D1_DIR, D2_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from correlate import correlate  # noqa: E402
from rca import analyze, load_history, load_json  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("aiops-serving")


class Alert(BaseModel):
    id: str
    ts: str
    service: str
    metric: str
    severity: str
    value: float | int
    threshold: float | int
    labels: dict[str, Any] = Field(default_factory=dict)


class IncidentRequest(BaseModel):
    alerts: list[Alert]


class RootCause(BaseModel):
    service: str
    root_cause_class: str = Field(alias="class")
    confidence: float
    graph_top3: list[list[Any]]
    method: str
    reasoning: str


class IncidentResponse(BaseModel):
    clusters: list[dict[str, Any]]
    root_cause: RootCause
    recommended_actions: list[str]
    similar_incidents: list[str]
    timings_ms: dict[str, float]
    version: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def json_log(message: str, **extra: Any) -> None:
    logger.info(json.dumps({"ts": utc_now(), "message": message, **extra}, ensure_ascii=False))


def load_static_state() -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    services_doc = load_json(D2_DIR / "dataset" / "services.json")
    history = load_history(D2_DIR / "dataset" / "incidents_history.json")
    graph_meta = {
        "graph_source": str(D2_DIR / "dataset" / "services.json"),
        "graph_loaded_at": utc_now(),
        "graph_version": services_doc.get("_meta", {}).get("schema_version", "manual-v1"),
        "graph_node_count": len(services_doc.get("services", [])) + len(services_doc.get("stores", [])),
        "graph_edge_count": len(services_doc.get("edges", [])),
    }
    return services_doc, history, graph_meta


SERVICES_DOC, HISTORY, GRAPH_META = load_static_state()


def primary_rca_result(rca_output: dict[str, Any], cluster_summary: dict[str, Any]) -> dict[str, Any]:
    cluster_sizes = {cluster["cluster_id"]: cluster["alert_count"] for cluster in cluster_summary["clusters"]}
    results = rca_output.get("results", [])
    if not results:
        return {
            "root_cause": "unknown",
            "class": "other",
            "confidence": 0.0,
            "graph_top3": [],
            "actions": ["Investigate manually"],
            "reasoning": "No RCA result was produced.",
            "similar_incidents": [],
            "method": "empty-fallback",
        }
    return max(results, key=lambda result: cluster_sizes.get(result["cluster_id"], 0))


def process_batch(alerts: list[dict[str, Any]]) -> dict[str, Any]:
    timings: dict[str, float] = {}

    start = time.perf_counter()
    cluster_summary = correlate(alerts, SERVICES_DOC, gap_sec=GAP_SEC, max_hop=MAX_HOP)
    timings["correlate"] = round((time.perf_counter() - start) * 1000, 3)

    start = time.perf_counter()
    rca_output = analyze(cluster_summary, alerts, SERVICES_DOC, HISTORY)
    timings["rca"] = round((time.perf_counter() - start) * 1000, 3)

    start = time.perf_counter()
    primary = primary_rca_result(rca_output, cluster_summary)
    response = {
        "clusters": cluster_summary["clusters"],
        "root_cause": {
            "service": primary["root_cause"],
            "class": primary["class"],
            "confidence": primary["confidence"],
            "graph_top3": primary["graph_top3"],
            "method": primary["method"],
            "reasoning": primary["reasoning"],
        },
        "recommended_actions": primary["actions"],
        "similar_incidents": primary["similar_incidents"],
        "timings_ms": timings,
        "version": APP_VERSION,
    }
    timings["serialize"] = round((time.perf_counter() - start) * 1000, 3)
    return response


app = FastAPI(title="GeekShop AIOps Incident API", version=APP_VERSION)


@app.middleware("http")
async def latency_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 3)
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    json_log(
        "request_complete",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict[str, Any]:
    checks = {
        "graph_loaded": GRAPH_META["graph_node_count"] > 0 and GRAPH_META["graph_edge_count"] > 0,
        "history_loaded": len(HISTORY) > 0,
        "llm_enabled": USE_LLM,
        "llm_required": False,
    }
    if not checks["graph_loaded"] or not checks["history_loaded"]:
        raise HTTPException(status_code=503, detail=checks)
    return {"status": "ready", "checks": checks}


@app.get("/version")
def version() -> dict[str, Any]:
    return {
        "app": APP_VERSION,
        "pipeline_config": {
            "gap_sec": GAP_SEC,
            "max_hop": MAX_HOP,
            "rca_method": RCA_METHOD,
            "use_llm": USE_LLM,
        },
        **GRAPH_META,
    }


@app.post("/incident", response_model=IncidentResponse)
def incident(request: IncidentRequest) -> dict[str, Any]:
    if not request.alerts:
        raise HTTPException(status_code=400, detail="alerts must not be empty")

    start = time.perf_counter()
    try:
        alerts = [alert.model_dump() for alert in request.alerts]
        timings = {"validate": round((time.perf_counter() - start) * 1000, 3)}
        output = process_batch(alerts)
        output["timings_ms"] = {**timings, **output["timings_ms"]}
        json_log(
            "incident_processed",
            cluster_count=len(output["clusters"]),
            root_cause=output["root_cause"]["service"],
            confidence=output["root_cause"]["confidence"],
        )
        return output
    except HTTPException:
        raise
    except Exception as exc:
        json_log("incident_failed", error=str(exc), traceback=traceback.format_exc())
        raise HTTPException(status_code=500, detail="incident pipeline failed") from exc
