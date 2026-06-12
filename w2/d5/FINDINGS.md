# FINDINGS

## A7. POC plan

Thành phần bất định nhất trong thiết kế là **tail sampling + correlation cho critical path payment/checkout**. Giả định cần validate đầu tiên: Grafana Tempo với OpenTelemetry tail sampling có thể giữ lại đủ traces quan trọng cho các lỗi hiếm như `payment-svc` connection pool exhaustion mà không làm trace cost vượt budget. Nếu có 3 ngày engineering time, tôi sẽ dựng POC trên `payment-svc`, `checkout-svc`, `payments-db` và chạy synthetic incident mô phỏng pool exhaustion. Measurement để confirm: ít nhất 95% request lỗi/high-latency có trace đầy đủ từ edge/checkout/payment/db trong Grafana, query trace dưới 10 giây, và trace ingest không vượt budget đã đặt cho critical path.

## 1. Capability khó thay thế nhất là gì, vì sao, và đã compromise gì?

Capability khó thay thế nhất là **log search + audit của Splunk Cloud**. Splunk không chỉ là nơi tìm log khi incident, mà còn phục vụ security/audit report và retention dài ngày. Compromise của thiết kế là tách log thành hai tier: **Grafana Cloud Logs/Loki** cho hot incident logs 15-30 ngày và **S3 + Athena/OpenSearch** cho cold audit logs 90-180 ngày. Đổi lại, cold audit query có thể chậm hơn Splunk hot search, nhưng chi phí log giảm từ khoảng **15.700 USD/tháng** xuống khoảng **629 USD/tháng** cho hot logs + cold tier.

## 2. Thiết kế đã trade resilience cho cost ở đâu?

Trade-off rõ nhất là đưa long-tail logs ra khỏi hot indexed Splunk để lưu ở S3 cold tier. Thiết kế tiết kiệm khoảng **15.071 USD/tháng** ở phần logs, nhưng trong scenario audit hoặc incident cần tìm log cũ hơn 30 ngày, query qua Athena/OpenSearch có thể chậm hơn vài phút so với hot index. Đây là trade-off chấp nhận được vì incident response nóng chủ yếu cần logs gần đây, còn audit không nằm trên đường xử lý Sev1/Sev2 realtime.

## 3. Nếu yêu cầu giảm budget là 60% thay vì 40%, quyết định nào đổi và quyết định nào không?

Thiết kế hiện tại đã giảm khoảng **76%**, nên vẫn đạt nếu yêu cầu là 60%. Các quyết định không đổi: dùng OpenTelemetry Collector, giữ tail sampling cho `payment-svc`/`checkout-svc`, tách hot/cold logs, và dùng Grafana IRM để correlation. Nếu phải giảm sâu hơn nữa, tôi sẽ xem lại số lượng user IRM/Grafana seat và synthetic checks, nhưng sẽ không cắt tracing critical path vì tracing là phần giúp giảm MTTR. Điều này cho thấy cost chính nằm ở **host-priced APM/infra** và **hot indexed logs**, không nằm ở Statuspage hay dashboard users.

## 4. Pattern thực tế nào được copy vào thiết kế?

Pattern được copy là **OpenTelemetry collector gateway + hot/cold telemetry tiering**, thường thấy trong các hệ thống production dùng cloud object storage để giữ raw logs dài ngày và dùng một observability backend nhanh cho hot incident data. Tôi điều chỉnh pattern này cho GeekShop bằng cách thêm policy theo criticality: `payment-svc`, `checkout-svc`, `edge-lb` giữ trace/error nhiều hơn, còn `notification-svc` và `recommender-svc` sample thấp hơn và không page độc lập nếu không ảnh hưởng SLO chính.

## 5. Unknown lớn nhất có thể derail migration ở tuần nào?

Unknown lớn nhất là **alert parity và paging behavior ở tuần 5-6**. Nếu Grafana IRM grouping không tái hiện đúng escalation/routing logic của PagerDuty, team có thể miss page hoặc mất niềm tin vào workflow mới. Tôi sẽ spike ngay tuần 1-2 bằng cách import 10 critical Datadog/PagerDuty alerts vào Grafana shadow mode và chạy synthetic incident cascade. Measurement để de-risk: synthetic checkout -> payment cascade chỉ tạo 1 grouped incident, đúng owner, đúng escalation, và on-call có thể đi từ incident sang dashboard/log/trace trong dưới 5 phút.
