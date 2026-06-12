# A5. Kế Hoạch Migration 8 Tuần

## Nguyên tắc migration

- Không có observability blackout trong giờ làm việc.
- Không tắt Datadog/Splunk/PagerDuty trước khi target path có parity.
- Mọi cut-over đều có rollback trong tối đa 30 phút.
- Chạy song song trước, cut over sau.
- Critical services được ưu tiên: `payment-svc`, `checkout-svc`, `edge-lb`, `auth-svc`, `catalog-db`.

## Week 1: Baseline, tagging chuẩn và OpenTelemetry pilot

Việc làm:

- Chuẩn hóa service labels: `service`, `team`, `env`, `criticality`, `owner_pager`.
- Deploy OpenTelemetry Collector ở staging.
- Instrument pilot cho `payment-svc`, `checkout-svc`, `catalog-svc`.
- Export song song telemetry sang Datadog hiện tại và Grafana Cloud target.
- Định nghĩa telemetry budget theo service: metrics series, log GB/ngày, trace sampling rule.

Go/no-go gate:

- 3 service pilot gửi được metrics/logs/traces sang Grafana.
- Không tăng error rate hoặc latency của app.
- Collector restart không làm mất telemetry quá 5 phút trong staging.

Rollback:

- Tắt OTel exporter ở service pilot.
- Quay lại chỉ dùng Datadog agent/Splunk forwarder như hiện tại.

## Week 2: Metrics path song song

Việc làm:

- Mở rộng OTel metrics cho 10 services và 4 backing stores.
- Tạo dashboard Grafana cho golden signals: latency, traffic, errors, saturation.
- Tạo dashboard riêng cho `payment-svc`, `checkout-svc`, `catalog-db`.
- Thiết lập cardinality guard: deny/drop labels như `customer_id`, raw `session_id`, raw `request_id`.

Go/no-go gate:

- 95% metric panels quan trọng có bản tương đương trong Grafana.
- Metric freshness p95 dưới 60 giây.
- Active series/service nằm trong budget.

Rollback:

- Giữ Datadog dashboard là source of truth.
- Disable remote write từ Collector sang Grafana nếu cardinality tăng bất thường.

## Week 3: Logs hot/cold routing song song

Việc làm:

- Route structured hot logs sang Loki.
- Route raw audit/security logs sang S3 cold tier.
- Thêm `trace_id` vào logs của critical services.
- Rebuild các saved searches quan trọng từ Splunk sang Grafana/Loki hoặc Athena.

Go/no-go gate:

- Query hot logs theo `service`, `severity`, `trace_id` trả kết quả dưới 10 giây cho window 24h.
- Audit team xác nhận 3 report quan trọng chạy được từ S3/Athena.
- Hot log ingest giảm ít nhất 40% so với 52GB/ngày baseline.

Rollback:

- Giữ Splunk Universal Forwarders hoạt động song song.
- Nếu Loki query chậm hoặc thiếu log, on-call quay lại Splunk trong vòng 30 phút.

## Week 4: Distributed tracing và tail sampling

Việc làm:

- Bật Tempo traces cho toàn bộ services.
- Tail sampling policy:
  - Giữ 100% traces có error.
  - Giữ 100% traces p99/high-latency.
  - Giữ sample cao cho `payment-svc`, `checkout-svc`, `edge-lb`.
  - Sample thấp hơn cho `notification-svc`, `recommender-svc`.
- Link Grafana dashboards từ metrics sang traces/logs.

Go/no-go gate:

- Synthetic incident payment timeout có trace đầy đủ từ edge/checkout/payment/db.
- Trace search theo `trace_id` từ log hoạt động.
- Trace ingest cost nằm trong target budget.

Rollback:

- Tắt tail sampling policy mới và quay về sampling đơn giản.
- Datadog APM vẫn giữ như fallback trong giai đoạn song song.

## Week 5: Alert parity và correlation

Việc làm:

- Recreate critical Datadog monitors trong Grafana Alerting.
- Tạo SLO burn-rate alerts cho checkout/payment availability.
- Tạo grouping rules trong Grafana IRM theo service, root-cause candidate và fingerprint.
- Mapping escalation policy từ PagerDuty sang IRM.

Go/no-go gate:

- 95% critical alerts có bản Grafana tương đương.
- Synthetic cascade checkout -> payment chỉ tạo 1 grouped incident chính, không tạo alert storm.
- On-call engineer triage được một synthetic incident chỉ bằng Grafana Explore + IRM.

Rollback:

- PagerDuty vẫn là paging source chính.
- Grafana alerts để non-paging hoặc shadow mode.

## Week 6: Paging cut-over có kiểm soát

Việc làm:

- Chuyển paging cho một team pilot, ưu tiên checkout/platform.
- IRM trở thành primary paging cho pilot; PagerDuty ở chế độ backup/manual fallback.
- Ghi lại incident timeline/action trong IRM.
- Runbook cập nhật link sang Grafana dashboard/log/trace.

Go/no-go gate:

- Pilot team xử lý thành công ít nhất 2 synthetic incidents.
- Không miss page trong 7 ngày.
- Escalation policy parity được team lead xác nhận.

Rollback:

- Re-enable PagerDuty integration làm primary trong vòng 30 phút.
- Tắt IRM paging, giữ Grafana alert shadow mode.

## Week 7: Log cost cut-over và Splunk de-scope

Việc làm:

- Giảm Splunk ingest cho app logs không còn cần hot search.
- Giữ Splunk read-only/limited cho audit transition nếu hợp đồng còn hiệu lực.
- Confirm S3 cold logs có lifecycle policy và access control.
- Finalize dashboard/report cho security team.

Go/no-go gate:

- Hot log volume trong target budget.
- Audit team xác nhận truy xuất được log 30/90 ngày từ cold tier.
- Không có incident nào trong tuần cần quay lại Splunk để tìm root cause chính.

Rollback:

- Re-enable Splunk forwarder route cho service bị thiếu log.
- Tạm tăng Loki retention/ingest budget nếu cần trong 1 tuần, nhưng không tắt cold tier.

## Week 8: Full production cut-over và cleanup

Việc làm:

- Grafana Explore + IRM trở thành primary observability workflow.
- Datadog/Splunk/PagerDuty chuyển sang fallback/read-only theo từng hợp đồng.
- Export dashboards, alert rules, IRM policies vào repo.
- Training final cho engineers và on-call.
- Chuẩn bị notice không gia hạn Splunk trước contract window.

Go/no-go gate:

- 100% critical services có dashboard, alert, runbook link.
- Median page-to-first-hypothesis trong drill giảm ít nhất 30%.
- Target monthly run-rate dưới 25.200 USD/tháng, tức giảm tối thiểu 40% so với 42.000 USD.
- Không có Sev1/Sev2 nào bị thiếu telemetry trong giai đoạn cut-over.

Rollback:

- Giữ license/contract hiện tại đủ lâu để bật lại Datadog/PagerDuty/Splunk integration.
- Nếu Grafana/IRM không đạt gate, gia hạn shadow period thêm 2 tuần và không decommission vendor cũ.

## No-observability-blackout guarantee

Trong toàn bộ 8 tuần:

- Datadog/Splunk/PagerDuty không bị tắt trước khi Grafana path đạt parity.
- Mọi collector/exporter thay đổi đều deploy ngoài giờ peak và có rollback.
- Critical alerts chạy song song ít nhất 2 tuần trước paging cut-over.
- On-call luôn có ít nhất một path query logs/traces/metrics đang hoạt động.
