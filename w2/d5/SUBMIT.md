# W2 Day 5 Submission

Đây là bài nộp cá nhân cho lab **Observability + AIOps Stack Redesign**.

Đọc theo thứ tự:

1. `architecture-target.png`
2. `components.md`
3. `cost-model.md`
4. `adr/adr-001-split-hot-and-cold-logs.md`
5. `adr/adr-002-standardize-on-otel-and-grafana-irm.md`
6. `migration-plan.md`
7. `risks.md`
8. `FINDINGS.md`
9. `README.md`

Thiết kế đề xuất dùng OpenTelemetry Collector, Grafana Cloud Metrics/Logs/Traces, S3 cold audit tier và Grafana IRM để giảm chi phí từ khoảng **42.000 USD/tháng** xuống khoảng **10.079 USD/tháng**, đồng thời cải thiện root-cause analysis bằng alert correlation và tail sampling.
