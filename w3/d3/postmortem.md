# Postmortem: Cloudflare-style WAF Regex CPU Saturation

**Status:** complete  
**Date:** 2026-06-18  
**Authors:** Le Kim Dung  
**Severity:** SEV2 (lab reproduction)  
**Duration:** 2.306 seconds (`01:49:17.803Z` to `01:49:20.109Z`)

## Summary

A candidate WAF regular expression with nested unbounded quantifiers was evaluated against an adversarial query on the synchronous request path. Match time increased from `0.097ms` with the safe expression to `1836.621ms`, a slowdown of approximately `18,934x`. The latency detector fired, correlation created an `edge-waf` incident, and RCA selected `edge-waf` with confidence `0.92`. Recovery occurred after the candidate rule was disabled and the isolated child process was cleaned up.

## Impact

- **Users affected:** one synthetic request; no production users
- **Services affected:** isolated `edge-waf` worker in the local reproduction
- **Revenue impact:** `$0` in the lab; a global hot-path rollout would affect every edge request
- **SLO budget consumed:** one request exceeded the `500ms` latency threshold; no production budget consumed
- **External communication:** not required for the local reproduction
- **Duration:** `2026-06-18 01:49:17.803Z` to `01:49:20.109Z`

## Timeline (UTC)

| Time | Event |
|---|---|
| 01:49:17.803 | Steady-state verification started. |
| 01:49:17.823 | Safe regex completed in `0.097ms`; probe passed. |
| 01:49:17.853 | Candidate WAF rule loaded into an isolated worker. |
| 01:49:17.883 | Adversarial query of length 24 entered the regex path. |
| 01:49:19.639 | Request completed after `1836.621ms`. |
| 01:49:19.759 | Latency detector crossed the `500ms` threshold. |
| 01:49:19.859 | Correlator created an incident cluster for `edge-waf`. |
| 01:49:19.939 | RCA selected `edge-waf` with confidence `0.92`. |
| 01:49:20.009 | Candidate rule was disabled by the rollback path. |
| 01:49:20.059 | Safe-regex latency returned below `10ms`. |
| 01:49:20.109 | Reproduction ended and the child process was cleaned up. |

## Root cause

The WAF execution path accepted a regular expression containing overlapping `.*` branches and nested repetition. For non-matching input, Python's backtracking engine explored an exponentially growing search space while holding the request worker. The deployment design lacked a static regex-complexity gate and staged canary evaluation before activation on the hot path.

## Contributing factors

1. Regex evaluation was synchronous and had no per-match timeout or worker isolation.
2. A latency SLI detected impact only after the slow request completed; it could not interrupt the evaluation.
3. RCA could identify `edge-waf` but could not identify the exact rule/version because deploy metadata was absent from alert evidence.
4. An error-rate-only detector would treat the eventual HTTP 200 as success and miss the user-visible stall.
5. A global rollout model would multiply one pathological rule across all workers without a canary buffer.

## Detection

- **How detected:** external latency measurement plus a `500ms` pipeline threshold
- **MTTD:** approximately `1.956s` from injection to alert
- **Could detection be earlier:** yes; pre-deploy ReDoS analysis and shadow evaluation would reject the rule before user traffic
- **Pipeline gap 1:** the alert identified latency/worker saturation but lacked a rule ID, pattern hash, and deployment version, limiting RCA from service level to config level
- **Pipeline gap 2:** a detector based only on 5xx/error rate would miss this outage because the slow request returned normally after `1836.621ms`

## Response

### What went well

- The reproduction ran in a child process with a five-second safety timeout.
- Latency-based detection captured a slow-success failure that error-rate monitoring would miss.
- Topology scope was unambiguous, so RCA selected the affected WAF layer.

### What went poorly

- Detection was reactive and waited for user-visible latency.
- Deploy metadata was not attached to the alert, so the rule itself was not ranked as the root artifact.
- The supplied Docker template has no Prometheus or live AIOps endpoint; alert/RCA artifacts were generated from measured reproduction evidence.

### Where the experiment was lucky

- Input length was limited to 24 characters; a longer input could have exceeded the timeout and exhausted a worker for much longer.
- Only one isolated process was affected, so there was no queue buildup across multiple requests.

## Action items

| Item | Owner | Due | Type | Priority |
|---|---|---|---|---|
| Add static ReDoS/complexity checks for every WAF regex | Security Platform | 2026-06-25 | preventive | P0 |
| Run candidate rules in shadow mode with hard CPU/time limits | Edge Platform | 2026-07-02 | preventive | P0 |
| Canary WAF rules at 1%, 10%, then 100% traffic | Release Engineering | 2026-07-02 | mitigation | P1 |
| Attach rule ID, hash, and deploy version to latency alerts | Observability | 2026-07-09 | detective | P1 |
| Add worker timeout and automatic rule kill switch | Edge Platform | 2026-07-09 | mitigation | P1 |
| Add slow-success SLI alongside 5xx availability | SRE | 2026-07-16 | detective | P2 |
