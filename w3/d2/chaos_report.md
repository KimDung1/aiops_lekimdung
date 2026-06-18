# Chaos Engineering Report - Le Kim Dung

> Execution mode: deterministic simulation. The official W3-D2 starter pack explicitly does not include the 10-service Docker stack, Prometheus, the `/alerts`/`/rca` API, Pumba, or Toxiproxy. The runner contains real command dispatchers, but this report uses evidence declared in `experiments.yaml`. It must not be represented as a production chaos run.

## 1. Setup

- Stack version: GeekShop topology from W2, simulated adapter, commit `pending-at-run-time`
- Pipeline version: W2 D1 correlation + W2 D2 graph/retrieval RCA
- Baseline window: 300 seconds per `baseline.json`
- Baseline steady state: external probe pass-rate `100%`, checkout p99 `180ms`, order success `99.8%`
- Total experiments run: 10
- Runner mode: `simulate`
- Real command support: Pumba, Docker, Toxiproxy dispatch is implemented in `build_inject_cmd()`

## 2. Results table

| # | Experiment | Detected | MTTD | RCA service | RCA correct | Probe during fault |
|---|---|---:|---:|---|---:|---:|
| 1 | payment_latency | Y | 28s | payment-svc | Y | 78% |
| 2 | payment_packet_loss | Y | 18s | payment-svc | Y | 74% |
| 3 | inventory_pod_kill | Y | 12s | inventory-svc | Y | 88% |
| 4 | api_cpu_saturation | Y | 35s | api-gateway | Y | 82% |
| 5 | payment_db_memory | Y | 42s | payment-db | Y | 71% |
| 6 | auth_clock_skew | N | - | - | N | 96% |
| 7 | log_collector_disk_fill | N | - | - | N | 100% |
| 8 | frontend_gateway_partition | Y | 15s | api-gateway | Y | 5% |
| 9 | dns_slow_lookup | Y | 55s | api-gateway | N | 69% |
| 10 | checkout_retry_storm | Y | 24s | payment-svc | Y | 77% |

Summary: detected `8/10`, RCA correct `7/8`, false alarms `1`, precision `0.889`, recall `0.800`, MTTD p50 `26s`, MTTD p95 `55s`. The run meets the assignment thresholds, but results are simulation evidence and require a future real-stack rerun.

## 3. Detailed per-experiment analysis

### Experiment 1 - payment latency

Hypothesis: a `500ms +/- 100ms` payment network delay should create a latency anomaly within 30 seconds and RCA should identify `payment-svc`. The simulated observation detected the fault in `28s`, while payment p99 rose from the `180ms` baseline to `735ms`. Checkout latency increased afterward, so temporal order and the caller-to-callee graph both pointed to payment rather than checkout. RCA returned `payment-svc`, matching ground truth. The external probe pass-rate fell to `78%`, which demonstrates user impact but remained above the experiment's 50% abort threshold. This is the expected strong case for the pipeline: the signal is user-visible, the dependency edge is explicit, and the root metric moves before downstream symptoms. The hypothesis passed.

### Experiment 2 - payment packet loss

Hypothesis: `30%` packet loss on payment should raise error rate, fire within 30 seconds, and produce payment as RCA root. Detection occurred in `18s`; payment error rate reached roughly `29%`, and checkout errors followed about six seconds later. The ordering matters because a naive count-based RCA could select checkout after retries amplify its alert volume. Graph and temporal evidence selected `payment-svc`, which matches expected ground truth. Probe pass-rate fell to `74%`, showing meaningful user harm, but rollback would prevent a longer budget burn. No baseline false alarm was associated with this experiment. This result suggests the detector is substantially more sensitive to abrupt error-rate changes than to subtle state faults such as clock skew. The hypothesis passed.

### Experiment 3 - inventory pod kill

Hypothesis: terminating one inventory instance should create an availability signal within 20 seconds and RCA should identify `inventory-svc`. The simulated `up` metric dropped to zero and checkout stock calls started returning 503 responses. Detection occurred in `12s`, the fastest MTTD in the run, and RCA correctly returned inventory. Probe pass-rate remained `88%` because only inventory-dependent checkout paths were affected; this partial impact is why a generic all-site probe alone is insufficient. The pipeline benefited from the explicit checkout-to-inventory topology edge and a direct availability signal. In a real stack, the key validation would be whether orchestration restarts the container before the detector's evaluation window observes it. The hypothesis passed under the configured 60-second repeated-kill window.

### Experiment 4 - API CPU saturation

Hypothesis: stressing one API gateway instance to `90%` CPU should cause user-facing latency above `500ms`, correlate downstream symptoms, and root the incident at `api-gateway`. Detection took `35s`, slower than direct availability and packet-loss faults because CPU itself is not used as an SLI; the detector waited for latency impact. Gateway CPU reached `91%`, and latency rose across all downstream calls. RCA selected `api-gateway`, which is correct because the broad fan-out pattern begins at the edge rather than at one dependency. Probe pass-rate dropped to `82%`. This experiment validates an important design choice from W3 D1: saturation is supporting evidence, while user latency is the paging signal. The hypothesis passed, although MTTD depends on latency-window length.

### Experiment 5 - payment database memory fill

Hypothesis: filling `payment-db` memory to `95%` should cause connection-pool pressure and RCA should identify the database rather than the louder payment application. Detection occurred in `42s`; database memory reached the injected target, followed by payment pool usage reaching `50/50` after about 31 seconds. RCA returned `payment-db`, matching ground truth. Probe pass-rate fell to `71%`, showing revenue-path impact. This result requires both state and temporal evidence: a simplistic graph algorithm might stop at `payment-svc`, while a terminal-node algorithm might always blame the database. The deciding evidence is that database degradation precedes application pool exhaustion. The hypothesis passed. A real run should confirm memory pressure does not trigger OOM-kill before graceful rollback executes.

### Experiment 6 - authentication clock skew

Hypothesis: shifting one auth instance by `+60s` should cause JWT/certificate failures, detection within 60 seconds, and RCA root `auth-svc`. The pipeline missed the fault. JWT errors increased, but the affected traffic share was only `25%` and aggregate 5xx stayed below the generic detector threshold. Probe pass-rate remained `96%`: below the 99% steady-state objective but not catastrophic. Because no incident was emitted, RCA had no cluster to analyze. The mismatch shows a detector coverage gap, not an RCA failure. Recommended fix: add an auth-specific SLI for token validation success and a clock-offset metric, then use a sustained low-priority burn-rate alert. The hypothesis failed, and this is one of two false negatives retained honestly in the scoreboard.

### Experiment 7 - log collector disk fill

Hypothesis: filling log-collector disk to `95%` should increase ingestion lag and be caught by meta-monitoring with `log-collector` as root. The pipeline stayed silent. The external user probe remained at `100%`, which is expected because the monitored application continued serving traffic; the failure affected observability rather than users immediately. No independent ingestion-lag monitor existed outside the log collection path, creating a monitoring dependency loop. Therefore the detector had no trustworthy input and RCA never ran. The hypothesis failed. The recommended fix is a separate meta-monitoring path that scrapes collector disk usage, queue lag, and last-ingested timestamp from outside the log stack. This experiment demonstrates why user probes and internal pipeline-health probes are complementary rather than interchangeable.

### Experiment 8 - frontend/gateway partition

Hypothesis: a complete 30-second partition between frontend and API gateway should trigger downstream timeout detection within 20 seconds and root the incident at the edge. Detection occurred in `15s`; external probe pass-rate collapsed to `5%`, and frontend network errors reached `94%`. RCA returned `api-gateway`, matching the experiment's expected edge root. The result is consistent with a broad failure affecting all downstream paths simultaneously. This fault also demonstrates the value of an external probe: internal application metrics could remain apparently healthy if requests never reach the gateway, while the probe immediately sees user-visible failure. The hypothesis passed. The rollback and recovery requirement is especially important here because a stale iptables rule could leave the system partitioned after the nominal experiment duration.

### Experiment 9 - DNS slow lookup

Hypothesis: adding `2s` DNS latency should create intermittent timeouts, be detected within 90 seconds, and RCA should identify `dns-resolver`. Detection occurred in `55s`, but RCA returned `api-gateway`, so detection passed and root-cause accuracy failed. Probe pass-rate dropped to `69%`. Evidence showed timeouts at the gateway, which was the first node represented in the current application graph; DNS was missing as an infrastructure dependency. This is a topology coverage gap. Recommended fix: model DNS as a shared dependency or shadow node and attach resolver latency/error evidence to affected services. One false alarm was counted in the baseline window, giving total precision `0.889`. The hypothesis only partially passed and supplies the run's single wrong-RCA case.

### Experiment 10 - checkout retry storm

Hypothesis: injecting `20%` HTTP errors at checkout should create a retry storm, and RCA must not choose checkout merely because it emits the most alerts. Detection occurred in `24s`. Checkout was the loudest service, but payment queue depth changed before the amplified checkout symptoms, so graph/temporal RCA returned `payment-svc`. The negative ground truth is `NOT checkout-svc`, making this result correct. Probe pass-rate fell to `77%`. This experiment directly validates the Week 2 RCA design: alert volume is not a reliable root-cause score, while dependency direction and temporal precedence are stronger signals. The hypothesis passed. In a real experiment, the injected error location must be carefully distinguished from the overloaded upstream service that turns retries into a sustained incident.

## 4. Gap analysis - top 3 pipeline weaknesses

### Gap 1 - State-specific detector coverage

- Symptom: experiment 6 was missed even though probe pass-rate fell to `96%` and JWT failures increased.
- Likely cause: the detector relies on generic latency/5xx thresholds and lacks auth-success or clock-offset signals.
- Recommended fix: add token-validation SLI, clock-offset telemetry, segmented thresholds per auth instance, and a sustained anomaly ticket before it becomes a full outage.

### Gap 2 - Monitoring dependency loop

- Symptom: experiment 7 filled collector disk to `95%`, but both detection and RCA were silent while the user probe stayed at `100%`.
- Likely cause: the observability pipeline depends on the component it is supposed to monitor.
- Recommended fix: deploy independent meta-monitoring that watches ingestion freshness, collector disk, and queue lag from a separate failure domain.

### Gap 3 - Incomplete infrastructure topology

- Symptom: experiment 9 was detected at `55s`, but RCA chose `api-gateway` instead of `dns-resolver`.
- Likely cause: DNS is absent from the service graph, so RCA can only rank the first visible application symptom.
- Recommended fix: enrich topology with DNS, service-mesh, queue, and shared-database nodes; require grounded evidence before returning high confidence.

## 5. Hypothesis for an unconfirmed gap

The API CPU experiment passed at one-instance scope, but it may fail differently when all gateway instances are stressed. A follow-up should escalate from one canary instance to 25%, 50%, then 100% of gateway capacity while preserving the same external probe. The hypothesis is that MTTD remains below 60 seconds, but RCA confidence drops because every downstream service degrades at nearly the same timestamp. This would test whether temporal scoring remains useful under simultaneous fan-out failure.
