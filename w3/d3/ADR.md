# ADR-001: Gate and Canary WAF Regex Changes Before Global Activation

## Status

Accepted

## Context

The Cloudflare-style reproduction measured `0.097ms` for a safe regex and `1836.621ms` for a nested-backtracking candidate, a slowdown of about `18,934x`. The pipeline detected the latency incident and selected `edge-waf`, but two gaps remained: the detector reacted only after a slow request completed, and RCA could not name the exact rule because alerts lacked deployment metadata. WAF rules execute on every request, so a global atomic rollout gives a pathological pattern the maximum possible blast radius. The platform needs a decision that prevents unsafe rules and limits impact when static analysis is incomplete.

## Decision

All WAF regex changes will pass a static ReDoS/complexity gate, execute in a timeout-isolated shadow environment, and roll out through 1%, 10%, and 100% traffic canaries with automatic rollback on latency burn-rate breach.

## Alternatives considered

1. **Keep global rollout with stronger monitoring**
   - **Pros:** simplest release flow, fastest propagation of security rules, no duplicate evaluation infrastructure.
   - **Cons:** monitoring remains reactive; one pathological rule can saturate all edge workers before rollback. It does not fix the observed pre-detection gap.
   - Rejected because detection after `1836.621ms` is already user impact.

2. **Use only static regex linting/ReDoS scanning**
   - **Pros:** cheap, deterministic, runs in CI, blocks many nested-quantifier patterns before deploy.
   - **Cons:** static tools can produce false positives/negatives and cannot model production input distribution or engine-specific runtime behavior.
   - Rejected as a standalone control, but retained as the first gate.

3. **Replace regex rules with a custom parser/finite-state engine immediately**
   - **Pros:** bounded runtime can eliminate catastrophic backtracking by construction.
   - **Cons:** high migration cost, compatibility risk, and slower delivery of security signatures.
   - Rejected for the current platform; considered a long-term direction for high-risk rule classes.

4. **LLM review of candidate rules**
   - **Pros:** can explain suspicious constructs and suggest simpler alternatives.
   - **Cons:** nondeterministic, can miss adversarial complexity, and is unsuitable as a security/reliability enforcement boundary.
   - Rejected as a mandatory gate; optional as developer assistance.

## Consequences

- **Positive:** unsafe patterns can be rejected before user traffic; canaries cap blast radius when analysis misses a case.
- **Positive:** rule ID/hash/version become first-class alert evidence, closing the RCA gap observed in reproduction.
- **Negative:** security-rule propagation becomes slower and requires shadow/canary infrastructure.
- **Negative:** false positives from static analysis may delay legitimate emergency rules.
- **Risk:** canary traffic may not contain the adversarial input. Mitigation: maintain a corpus of worst-case strings and fuzz candidate patterns.
- **Risk:** timeout isolation may add request overhead. Mitigation: benchmark at p99/p99.9 and apply isolation only to untrusted/high-risk patterns.
- **What gets locked in:** staged WAF delivery and deploy metadata become part of the edge platform contract.
