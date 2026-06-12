# Bài Nộp Observability + AIOps Stack Redesign

Đọc theo thứ tự sau:

1. `architecture-target.png` để xem kiến trúc target.
2. `components.md` để hiểu vì sao chọn từng component/vendor.
3. `cost-model.md` để kiểm tra chi phí hiện tại, chi phí target và mức giảm khoảng 76%.
4. `adr/` để xem hai quyết định kiến trúc khó nhất.
5. `migration-plan.md` để xem kế hoạch migration 8 tuần có rollback và go/no-go gate.
6. `risks.md` để xem risk register.
7. `FINDINGS.md` để xem reflection và POC plan.

Thiết kế đề xuất dùng OpenTelemetry Collector làm ingestion layer, Grafana Cloud Metrics/Logs/Traces làm hot observability backend, S3 làm cold audit tier, và Grafana Alerting/IRM làm alert correlation + paging workflow. Mục tiêu là giảm chi phí từ khoảng **42.000 USD/tháng** xuống khoảng **10.079 USD/tháng** mà vẫn giữ năng lực incident response cho các service quan trọng như `payment-svc`, `checkout-svc`, `edge-lb` và `catalog-db`.
