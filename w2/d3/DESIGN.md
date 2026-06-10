# DESIGN - W2-D3 Model Serving

## Pipeline architecture

`serve.py` exposes the alert correlation and RCA pipeline as a FastAPI service. The main endpoint is `POST /incident`, which receives a JSON body with `alerts`. Pydantic validates the request schema first. The endpoint then converts the Pydantic objects into plain dictionaries and calls the real Day 1 `correlate()` function with `gap_sec = 120` and `max_hop = 1`. The correlation output is passed into the real Day 2 `analyze()` RCA function, which ranks graph candidates and enriches the result with incident-history retrieval. The response returns `clusters`, `root_cause`, `recommended_actions`, `similar_incidents`, `timings_ms`, and `version`.

## Endpoints

- `GET /healthz`: liveness check. It only proves the process is alive.
- `GET /readyz`: readiness check. It verifies service graph and incident history are loaded.
- `GET /version`: app version, graph metadata, and pipeline config.
- `POST /incident`: runs correlation + RCA end to end.

## Latency budget

I measured 20 sequential requests using the real 20-alert dataset. The endpoint returned p50 `1.69ms` and p99 `2.263ms`. The measured phase breakdown from a representative response was: validate `0.059ms`, correlate `0.193ms`, RCA `0.39ms`, serialize `0.003ms`. RCA is the largest local phase because it runs candidate scoring and retrieval. If input grows 10x, validation, correlation, and RCA grow with alert/cluster size; static state loading is fixed because graph and history are cached at import time.

## Production concern

The service is designed to be stateless per request. `SERVICES_DOC` and `HISTORY` are loaded once at startup and treated as read-only, so concurrent requests do not mutate shared state. With one worker, the measured concurrency test using 20 requests at concurrency 4 returned 0 errors, p50 `4.599ms`, p99 `19.819ms`. If this became production, I would either reload graph/history on a timer or deploy new graph versions explicitly and expose them through `/version`.

## FastAPI trade-off

I chose FastAPI instead of Flask because the assignment requires a production-style API with schema validation. FastAPI gives Pydantic validation, OpenAPI docs, async-compatible middleware, and clean endpoint typing. Flask would work for a prototype but would require manual validation. BentoML is useful when the core artifact is a model package; this project is a custom AIOps pipeline, so FastAPI is simpler and more direct.

## Fault tolerance

The implementation does not call an external LLM by default: `AIOPS_USE_LLM=false`. That means `/readyz` does not fail if an LLM provider is down. If a future LLM enrichment layer is enabled, the service should keep graph+retrieval as fallback and use timeout + retries for the provider call.
