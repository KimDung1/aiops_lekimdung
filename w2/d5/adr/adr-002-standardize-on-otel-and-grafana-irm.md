# ADR-002: Chuẩn Hóa Ingestion Bằng OpenTelemetry Và Incident Workflow Bằng Grafana IRM

## Status

Accepted.

## Context

Kiến trúc hiện tại có nhiều công cụ chồng chéo:

- Datadog là primary single pane cho engineers.
- Splunk dùng cho long-tail logs và audit.
- PagerDuty dùng cho paging/routing.
- Grafana chỉ là dashboard mirror cho executive dashboards.

Khi có multi-service incident, on-call phải mở khoảng 4 UI để tự nối dữ liệu. Pain point ghi nhận median time từ lúc nhận page đến first hypothesis là khoảng **8 phút** trong các incident nhiều service. PagerDuty cũng nhận alert theo cluster, ví dụ cascade có thể tạo nhiều incident rời rạc.

Trong lịch sử incident, các lỗi critical thường nằm ở critical path:

- `payment-svc` và `payments-db`: connection pool exhaustion, lock contention, thread starvation.
- `checkout-svc`: cascade sang cart, payment, inventory, notification.
- `catalog-db`: shared bottleneck cho catalog, search, inventory, recommender.
- `edge-lb`: DDoS/config/TLS gây ảnh hưởng toàn hệ thống.

Vì vậy thiết kế cần correlation theo service graph, không chỉ paging từng alert đơn lẻ.

## Decision

Chọn:

- **OpenTelemetry Collector** làm ingestion path chuẩn cho metrics, logs, traces.
- **Telemetry policy layer** để sampling, redaction, cardinality guard.
- **Grafana Cloud Metrics/Logs/Traces** làm storage/query layer chính.
- **Grafana Alerting + IRM** làm alert grouping, incident routing và paging.
- **Grafana Explore** làm query surface chính cho on-call.

PagerDuty sẽ được thay dần bằng Grafana IRM sau khi alert parity và escalation policy parity đạt go/no-go gate.

## Alternatives considered + rejected

### Alternative 1: Giữ Datadog làm primary platform, chỉ tối ưu sampling/log volume

Rejected vì vẫn giữ cost model host-based và custom metrics overage. Cách này có thể giảm một phần logs nhưng khó giảm đủ 40% mà vẫn tránh future cardinality surprise.

### Alternative 2: Dùng hoàn toàn OSS self-hosted: Prometheus/Mimir, Loki, Tempo, Alertmanager

Rejected vì chi phí vendor thấp hơn nhưng operational risk cao hơn. Team hiện đã bị cognitive load bởi observability stack; nếu tự vận hành toàn bộ critical observability plane, có thể tiết kiệm tiền nhưng tăng rủi ro blackout và yêu cầu skill quá nhanh.

### Alternative 3: Giữ PagerDuty cho paging, chỉ dùng Grafana cho dashboard/query

Rejected vì pain point lớn là alert grouping/correlation. Nếu Grafana biết service graph nhưng PagerDuty chỉ nhận alert rời rạc, on-call vẫn phải tự correlate trong incident.

## Consequences

Tích cực:

- Giảm số UI chính của on-call từ 4 xuống 2: Grafana Explore và Grafana IRM.
- Alert có thể link trực tiếp sang dashboard, logs và traces.
- Tail sampling giữ lại trace quan trọng hơn random sampling 1%.
- OpenTelemetry giảm vendor lock-in vì instrumentation và pipeline không bị khóa vào Datadog.
- Grafana IRM giảm PagerDuty seat cost từ **3.900 USD/tháng** xuống khoảng **1.300 USD/tháng**.

Tiêu cực:

- Grafana Cloud trở thành dependency lớn hơn trong target state.
- Team phải migrate alert rules, escalation policies và dashboard queries.
- IRM workflow khác PagerDuty, cần diễn tập on-call trước khi cut over.
- Nếu Grafana Cloud có incident, team cần fallback runbook cho critical dashboards/alerts.

## Follow-up controls

- Chạy song song Datadog/PagerDuty và Grafana trong migration.
- Chỉ cut over paging khi 95% critical alerts có parity.
- Tổ chức synthetic incident drill cho payment connection pool exhaustion trước khi go-live.
- Export Grafana dashboards/alerts định kỳ để giữ exit path.
