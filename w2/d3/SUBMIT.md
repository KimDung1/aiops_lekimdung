# SUBMIT - W2-D3 Model Serving

## 1. Latency measurement

I ran the endpoint with 20 sequential `POST /incident` requests using the real 20-alert dataset. The response header `X-Response-Time-Ms` showed p50 `1.69ms` and p99 `2.263ms`. The representative internal timing was validate `0.059ms`, correlate `0.193ms`, RCA `0.39ms`, serialize `0.003ms`. The largest phase is RCA because it runs graph/temporal scoring plus incident-history retrieval. If input grows 10x, validation and correlation scale with alert count, while RCA scales mostly with number of clusters and cluster size. Static graph/history loading is fixed cost because it happens once at startup.

## 2. LLM down or four concurrent requests

I tested 20 requests with concurrency 4 using `ThreadPoolExecutor`. The endpoint returned 0 errors, with p50 `4.599ms` and p99 `19.819ms`. The first bottleneck I observed was not CPU; it was logging/stdout handling during benchmark when server output was piped and not consumed. With stdout redirected, requests were stable. The fallback path is built in: `AIOPS_USE_LLM=false` by default, so the service uses graph+retrieval only. If an LLM provider is down, the endpoint can still return root cause candidates, class, actions, and similar incidents from local data.

## 3. healthz vs readyz

`/healthz` only checks liveness: it returns `{"status": "ok"}` if the process is running. `/readyz` checks readiness: graph data is loaded, incident history is loaded, and the service is able to process real incident requests. I keep them separate because a process can be alive but not ready to serve traffic if dataset loading failed. Since LLM is optional in this implementation, `/readyz` still passes when LLM is disabled or unavailable. That is intentional because local graph+retrieval is the primary production fallback path.

## Run commands

```bash
uvicorn serve:app --host 0.0.0.0 --port 8000 --workers 1
```

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
curl -X POST http://localhost:8000/incident -H "Content-Type: application/json" --data @sample_request.json
```
