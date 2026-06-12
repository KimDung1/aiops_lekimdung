# ADR-001: Tách Hot Logs Và Cold Audit Logs

## Status

Accepted.

## Context

Stack hiện tại dùng Splunk Cloud cho long-tail log search và audit với chi phí khoảng **13.900 USD/tháng**, đồng thời Datadog Logs vẫn index một phần hot logs với chi phí khoảng **1.800 USD/tháng**. Tổng phần log hot/indexed hiện tại khoảng **15.700 USD/tháng**, là một trong các cost driver lớn nhất.

Pain point liên quan:

- Log search latency vượt 25 giây khi query window qua 7 ngày.
- Splunk index rotation thỉnh thoảng làm saved search trả rỗng trong 5-15 phút.
- On-call phải mở Datadog Logs và Splunk cùng lúc trong incident.
- Compliance/security vẫn cần audit logs, nên không thể đơn giản xóa log.

Vì vậy quyết định khó không phải là "có giữ logs hay không", mà là **log nào cần hot searchable và log nào chỉ cần retention/audit**.

## Decision

Tách log thành hai tier:

- **Hot incident logs**: gửi vào **Grafana Cloud Logs / Loki**, giữ khoảng 15-30 ngày, ưu tiên structured logs có label `service`, `env`, `severity`, `trace_id`, `incident_id`.
- **Cold audit logs**: gửi vào **S3** giữ 90-180 ngày, query bằng Athena/OpenSearch ad-hoc khi audit/security cần.

OpenTelemetry Collector và telemetry policy layer đứng trước cả hai tier để:

- Redact PII.
- Drop debug/noisy logs khỏi hot tier.
- Route security/audit logs sang cold tier.
- Giữ `trace_id` để link logs với traces trong Grafana.

## Alternatives considered + rejected

### Alternative 1: Giữ Splunk Cloud làm log platform chính

Rejected vì Splunk hiện là cost driver lớn và vẫn gây pain point về search latency/index rotation. Giữ Splunk sẽ làm khó đạt yêu cầu giảm ít nhất 40% cost nếu không cắt capability khác nguy hiểm hơn.

### Alternative 2: Chuyển toàn bộ logs sang Loki, bỏ cold tier

Rejected vì security/audit team vẫn cần retention dài ngày. Nếu chỉ dùng Loki cho mọi log dài ngày, chi phí hot/search tier có thể tăng lại và thiết kế không giải quyết triệt để bài toán retention economics.

### Alternative 3: Chỉ lưu logs vào S3, bỏ hot search

Rejected vì làm giảm incident-response capability. On-call vẫn cần query log nhanh trong 15-30 ngày gần nhất, đặc biệt cho payment/checkout/catalog incidents.

## Consequences

Tích cực:

- Giảm mạnh chi phí log hot/indexed từ khoảng **15.700 USD/tháng** xuống khoảng **429 USD/tháng** cho hot logs và khoảng **200 USD/tháng** cho cold audit tier.
- On-call dùng Grafana Explore để query logs cùng metrics/traces.
- Audit logs vẫn được giữ, không mất compliance posture.
- Có thể kiểm soát log volume trước khi vào vendor.

Tiêu cực:

- Query cold logs qua Athena/OpenSearch sẽ chậm hơn Splunk hot search.
- Team phải học Loki label model và viết structured logging nhất quán.
- Cần kiểm soát label cardinality trong logs; nếu label quá tự do, Loki có thể bị giảm performance.
- Security team cần điều chỉnh report/query từ Splunk sang S3/Athena trong migration.

## Follow-up controls

- Thiết lập log budget theo service: GB/ngày và label cardinality.
- Bắt buộc `trace_id` trong structured logs cho critical services.
- Giữ Splunk read-only trong giai đoạn transition cho đến khi audit report quan trọng chạy được trên S3/Athena.
