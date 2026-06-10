# SUBMIT - W2-D2 RCA

## 1. Confidence của top-1 trong cluster lớn nhất

Cluster lớn nhất là `c-001-000`, gồm 18 alert. Top-1 là `payment-svc` với confidence `0.95`. Nếu phải đặt threshold cho auto-rollback không cần SRE confirm, tôi sẽ chọn khoảng `0.98` cộng thêm điều kiện deploy/version hiện tại phải khớp incident history hoặc change event gần nhất. Với confidence `0.95`, tôi dám auto-page đúng team và mở runbook, nhưng rollback trực tiếp vẫn hơi rủi ro vì action trong history có thể nhắc version cũ, ví dụ `v2.6`, không chắc trùng với deploy hiện tại.

## 2. Variant classifier đã chọn

Tôi chọn variant A: rule-based + retrieval, không dùng free hoặc paid LLM. Cách chạy thực tế là graph + temporal scorer tạo `graph_top3`, sau đó retrieval top-3 từ `incidents_history.json` bằng overlap service, severity, và root candidate. Classifier lấy `root_cause_class` và remediation từ incident giống nhất. Trade-off là output ít linh hoạt hơn LLM, nhưng deterministic, không cần API key, dễ debug, và phù hợp auto-grader. LLM có thể giải thích tự nhiên hơn, nhưng cần schema validation và hallucination guard.

## 3. Pipeline giống product nào nhất?

Pipeline này gần Dynatrace Davis nhất vì giả định service graph là nguồn sự thật chính, rồi dùng graph traversal để rank root cause trong cluster. Với GeekShop, lựa chọn này hợp lý vì service map tương đối ổn định và incident chính là cascade theo dependency rõ ràng: `payment-svc` làm `checkout-svc` và `edge-lb` bị ảnh hưởng. Nếu hệ thống chuyển sang event-driven phức tạp hoặc graph thiếu edge, tôi sẽ bổ sung causal inference từ time-series hoặc trace data, gần hướng Causely hơn.

## Implementation notes

Output cuối nằm ở `results/rca_output.json`. Notebook có thể chạy lại offline, không cần API key. Pipeline có fallback nếu retrieval rỗng hoặc class không nằm trong enum chính: giữ top-1 graph candidate, class `other`, action `Investigate manually`.
