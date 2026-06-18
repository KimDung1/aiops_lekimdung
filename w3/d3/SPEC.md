# AIOps Mini-Platform Spec - Le Kim Dung

## 1. Platform overview

The mini-platform monitors a GeekShop-style e-commerce stack and supports anomaly detection, alert correlation, root-cause ranking, SLO burn-rate alerting, and incident response. Its primary users are SRE/on-call engineers who need fewer alerts, faster triage, and reproducible evidence. The platform does not autonomously perform destructive remediation; rollback requires confidence and guardrails.

## 2. SLO definition (from W3-D1)

| Service | SLI | Target | Monthly budget |
|---|---|---:|---:|
| Frontend | DOM ready `<3000ms`, no JS/network error | 99% | 51,840 bad RUM events / ~432 min |
| API | 2xx/3xx under `500ms`; 5xx/429 are failures | 99.9% | 20,738 failed requests / ~43 min |
| Database | successful query under `100ms` | 99.95% | 863 failed/slow queries / ~22 min |

Burn-rate tiers use `1h/5m`, `6h/30m`, and `3d/6h` windows. API tier 1 was tuned from `14.4` to `10`, producing `86.4%` noise reduction, `0` false negatives, and `0s` MTTD delta on replay validation.

## 3. Detection + Correlation + RCA stack (from W1+W2)

**Detection:** streaming rules analyze memory, GC, traffic, queue, latency, 5xx, and dependency timeout signals. Two-of-three confirmation reduces one-point noise, while a cooldown prevents repeated alerts.

**Correlation:** fingerprint metadata, a 120-second session window, and service topology with `max_hop=1` reduce 20 alerts to 3 clusters (`0.85` reduction ratio). Alerts explicitly marked unrelated/noise remain singleton clusters.

**RCA:** ADR-001 favors graph + temporal scoring, enriched by retrieval from incident history. The main W2 incident ranked `payment-svc` / `connection_pool_exhaustion` at confidence `0.95`. The method returns top-3 candidates and falls back to graph-only output when retrieval is unavailable.

## 4. Reliability validation (from W3-D2)

- Chaos cadence target: weekly simulation in CI, monthly real-stack staging run, quarterly canary game day.
- Detection target: at least 70%; simulation observed `8/10` (`80%`).
- RCA target: at least 70% among detected; simulation observed `7/8` (`87.5%`).
- False alarms target: at most 1 per baseline windows; observed `1`.
- MTTD: p50 `26s`, p95 `55s`.
- Steady state: external synthetic probe plus internal metrics.
- Top gaps: clock-skew detector coverage, independent meta-monitoring, and missing DNS topology.

The W3-D2 starter pack omitted the service stack/chaos binaries, so those figures are deterministic simulation evidence and require real-stack confirmation.

## 5. Operational pattern (from W3-D3)

The platform uses the Google-style blameless postmortem in `postmortem.md`, with a timestamped timeline, system-focused root cause, contributing factors, response review, and owned/due action items. The Cloudflare-style reproduction measured a regex slowdown from `0.097ms` to `1836.621ms` (`18,934x`). ADR-001 requires static ReDoS checks, isolated shadow execution, staged canaries, and rule metadata in alert evidence. On-call pages use SLO burn severity; tickets handle slower capacity/leading indicators.

## 6. Cost model (from W3-D3)

For the current GeekShop scenario:

- Services: 35
- Incidents: 4/month
- Average duration: 1.5 hours
- Downtime cost: `$15,000/hour`
- Expected MTTR reduction: 40%
- AIOps monthly cost: `$18,000`
- Monthly value: `$36,000`
- ROI: `2.0`
- Payback: `0.5` month
- Verdict: `worth_it`

Break-even occurs when avoided downtime value exceeds `$18,000/month`, equivalent to 3 downtime hours saved at `$15,000/hour` with a 40% reduction assumption.

## 7. Open risks

1. **High - stale topology:** missing DNS/infrastructure nodes can produce confident wrong RCA. Mitigation: derive graph edges from traces/mesh and version graph snapshots.
2. **High - monitoring dependency loop:** collector failure can hide telemetry. Mitigation: separate meta-monitoring failure domain and external freshness probes.
3. **Medium - state-specific detector gaps:** clock skew/JWT failures may remain below generic 5xx thresholds. Mitigation: domain-specific SLI and clock-offset telemetry.
4. **Medium - LLM/retrieval confidence:** historical similarity may suggest obsolete actions. Mitigation: require evidence links and current deploy metadata before remediation.
5. **Medium - simulation-to-production gap:** W3-D2 chaos evidence is not a real stack run. Mitigation: execute the same catalog in staging with Pumba/Toxiproxy before production approval.
