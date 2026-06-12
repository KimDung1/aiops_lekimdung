# A6. Risk Register

| Risk | Likelihood | Impact | Mitigation cụ thể | Owner |
|---|---|---|---|---|
| Loki label cardinality tăng cao vì team thêm label như `customer_id` hoặc raw `request_id`. | Medium | High | Áp dụng denylist label ở OpenTelemetry Collector; alert khi active label cardinality/service vượt budget; review schema log trong CI. | Platform observability lead |
| Tail sampling policy cấu hình sai làm mất trace quan trọng của payment/checkout. | Medium | High | Chạy shadow mode 2 tuần; synthetic incident payment timeout phải chứng minh có đủ edge -> checkout -> payment -> db trace trước cut-over. | SRE tracing owner |
| Security/audit team không migrate kịp report từ Splunk sang S3/Athena. | Medium | Medium | Giữ Splunk read-only trong transition; chọn 3 audit report quan trọng nhất làm go/no-go gate tuần 3 và tuần 7. | Security engineering lead |
| Grafana IRM escalation policy không tương đương PagerDuty, dẫn tới miss page. | Low | High | Chạy pilot một team trước; PagerDuty giữ backup/manual fallback; yêu cầu 7 ngày không miss page trước full cut-over. | Incident commander |
| Engineers chưa quen Grafana Explore/Loki/Tempo nên MTTR tăng trong tháng đầu. | Medium | Medium | Tổ chức 2 incident drills: payment pool exhaustion và catalog-db slow query; cập nhật runbook có link dashboard/log/trace. | Engineering managers |
| Splunk contract notice window bị lỡ, làm team vẫn phải trả tiền dù đã migrate. | Medium | High | Tạo calendar owner rõ ràng; gửi notice không gia hạn trước 90 ngày; nhờ procurement xác nhận bằng email và lưu vào repo governance. | Procurement + platform manager |
