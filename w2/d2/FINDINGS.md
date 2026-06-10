# FINDINGS - W2-D2 RCA

## Main cluster RCA

Cluster chính là `c-001-000`, gồm `payment-svc`, `checkout-svc`, `edge-lb`, `cart-svc`, và `notification-svc`. RCA pipeline chọn root cause là `payment-svc` với class `connection_pool_exhaustion`, confidence `0.95`. Lý do chính là `payment-svc` đứng sâu trong graph của luồng checkout: `edge-lb` gọi `checkout-svc`, `checkout-svc` gọi `payment-svc`. Khi payment degrade, lỗi lan ngược lên checkout và edge. Temporal signal cũng ủng hộ vì alert payment xuất hiện rất sớm trong cluster. Retrieval layer tìm được các incident giống như `INC-2025-09-05` và `INC-2025-11-08`, đều là payment connection pool exhaustion.

## Confidence and auto-remediation

Tôi tin output này đủ mạnh để đề xuất remediation, nhưng chưa nên auto-rollback hoàn toàn nếu không có guardrail. Confidence cao vì graph, timestamp, và history đều đồng thuận. Tuy nhiên, action lấy từ incident cũ là `Rollback v2.6...`, trong khi incident hiện tại có thể là version khác. Tôi sẽ cho phép auto-remediation dạng an toàn hơn như tăng observability, page đúng owner, hoặc mở runbook. Với rollback, tôi muốn threshold cao hơn và cần xác nhận deploy/version hiện tại trước khi tự động chạy.

## Uncertain case

Case tôi không chắc nhất là cluster `c-001-002` của `search-svc`. Đây là singleton cluster nên graph scorer đương nhiên cho `search-svc` điểm cao, nhưng retrieval trả về nhiều pattern khác nhau: cache cold start, N+1 query, slow query qua catalog-db. Vì class từ history gần nhất không nằm trong enum chính nên output fallback về `other`. Với dữ liệu chỉ có một alert, RCA không đủ evidence để phân biệt cache cold start, query issue hay dependency catalog-db. Cần thêm metric time-series hoặc log context.

## Bonus choice

Tôi không chọn bonus LLM/TF-IDF/decision tree vì retrieval-only đã đủ cho acceptance criteria và dataset nhỏ. Với 3 cluster từ bài này, graph + temporal scorer đã chọn root cause hợp lý, còn kNN-style retrieval đã map được class/action cho cluster chính. Dùng LLM trong bài này có thể làm output đẹp hơn, nhưng cũng thêm rủi ro hallucination và cần validate chặt hơn. Với production thật, tôi sẽ thêm LLM sau khi graph/retrieval baseline đã ổn định.
