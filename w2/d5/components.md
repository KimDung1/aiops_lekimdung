# A2. Bảng Quyết Định Thành Phần

## Nguyên tắc thiết kế

Thiết kế mới ưu tiên ba mục tiêu:

- Giảm chi phí tối thiểu 40% so với mức hiện tại khoảng **42.000 USD/tháng**.
- Giảm thời gian tìm root cause bằng cách gom metrics, logs, traces và alert correlation vào một workflow.
- Không làm mất năng lực incident response cho các service critical như `payment-svc`, `checkout-svc`, `edge-lb` và các backing store quan trọng.

## Bảng quyết định

| Capability | Component/vendor chọn | Vì sao chọn component này? | Nếu đổi ý sau 6 tháng thì điều gì xấu đi? |
|---|---|---|---|
| Metrics ingestion | OpenTelemetry Collector | Collector là chuẩn mở, gom telemetry từ 10 service vào một pipeline và giảm phụ thuộc Datadog agent. | Nếu bỏ OpenTelemetry, team quay lại phụ thuộc vendor agent và migration sau này tốn công hơn. |
| Metrics storage + query | Grafana Cloud Metrics / Mimir | PromQL-compatible, tích hợp trực tiếp với Grafana dashboard/alerting và tránh chi phí host-based Datadog. | Nếu đổi sang Datadog/New Relic, chi phí theo host và custom metric dễ tăng lại khi service/cardinality tăng. |
| Logs ingestion | OpenTelemetry Collector + policy processor | Có thể filter, redact, route hot/cold logs trước khi gửi sang vendor hoặc S3. | Nếu gửi thẳng log vào vendor, team mất điểm kiểm soát chính để giảm log volume và PII risk. |
| Logs storage + search | Grafana Cloud Logs / Loki cho hot logs, S3 + Athena/OpenSearch cho cold audit logs | Loki phù hợp incident log theo label/service; S3 giữ audit dài ngày rẻ hơn Splunk hot index. | Nếu quay lại Splunk hot index cho toàn bộ logs, chi phí log sẽ lại là cost driver lớn nhất. |
| Distributed tracing | Grafana Cloud Traces / Tempo + tail sampling | Tail sampling giữ 100% error/high-latency traces cho critical path thay vì random sampling 1%. | Nếu bỏ tail sampling, các lỗi hiếm như DB pool exhaustion hoặc p99 latency spike có thể lại bị mất trace. |
| Alerting rule engine | Grafana Alerting | Alert rule nằm gần metrics/logs/traces, dễ link từ alert sang dashboard và trace. | Nếu tách rule engine sang tool khác, on-call lại phải chuyển UI và correlation giảm. |
| Alert correlation / grouping | Grafana IRM | IRM gom alert theo fingerprint, service và dependency path để giảm alert storm. | Nếu giữ PagerDuty thuần routing, cascade nhiều service vẫn dễ tạo hàng chục incident rời rạc. |
| Incident routing + paging | Grafana IRM | Giảm seat cost so với PagerDuty hiện tại và nằm cùng workflow Grafana. | Nếu đổi lại PagerDuty, routing quen thuộc hơn nhưng chi phí cao hơn và correlation yếu hơn nếu không mua thêm capability. |
| Dashboards | Grafana | Grafana đã tồn tại trong stack, giờ trở thành primary UI thay vì dashboard mirror. | Nếu dùng nhiều dashboard tool, onboarding và cognitive load của on-call tiếp tục cao. |
| SLO tracking | Grafana SLO dashboards + PromQL burn-rate alerts | SLO burn-rate alert phù hợp với checkout/payment availability và dễ query bằng PromQL. | Nếu không chuẩn hóa SLO ở Grafana, alert vẫn thiên về metric đơn lẻ thay vì user-impact. |
| Status page | Giữ Statuspage | Chi phí thấp, không phải pain point chính, migration không đem lại nhiều lợi ích. | Nếu thay Statuspage, rủi ro quy trình customer communication tăng nhưng tiết kiệm không đáng kể. |

## Mapping theo pain point

| Pain point hiện tại | Thiết kế mới xử lý bằng gì? |
|---|---|
| Log search chậm khi vượt 7 ngày | Hot logs ở Loki cho incident gần; long-tail logs đưa sang S3/Athena cho audit, không đặt trên hot path. |
| Trace sample 1% | Tempo tail sampling giữ lỗi và high-latency traces. |
| Không có service-graph alert correlation | Grafana IRM grouping theo fingerprint/service/dependency. |
| Custom metric cardinality explosion | Policy processor drop/block label nguy hiểm như `customer_id`. |
| PagerDuty alert storm | IRM grouped incidents, chỉ page incident đại diện. |
| Splunk index rotation ảnh hưởng dashboard | Dashboard incident không phụ thuộc Splunk hot index. |
| Không có audit trail incident decision | IRM incident timeline làm system of record. |
| Onboarding mất 2-3 tuần | Giảm từ 4 UI chính xuống 2 UI: Grafana Explore và Grafana IRM. |
| Không query được pattern incident theo service/action | IRM timeline + structured labels cho service/action. |
| Vendor lock-in | OpenTelemetry giữ telemetry pipeline portable; cold logs nằm trong S3 của team. |
