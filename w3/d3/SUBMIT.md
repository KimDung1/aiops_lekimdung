# W3-D3 Submission - Le Kim Dung

## Outage chosen

- ID: 3
- Name: Cloudflare WAF Regex, 2019-07-02
- Why this one: Tôi chọn outage này vì một thay đổi cấu hình rất nhỏ có thể tạo CPU/latency failure toàn cầu khi nằm trên hot path. Failure mode có thể tái tạo tối thiểu và đo trực tiếp mà không cần sao chép toàn bộ edge infrastructure.
- Failure mode: catastrophic backtracking + global rollout without canary

## 3 thứ tôi học từ outage này

1. HTTP 200 không đồng nghĩa user experience tốt. Evil regex trả kết quả nhưng mất `1836.621ms`, vì vậy error-rate-only alert sẽ miss.
2. Detection nhanh vẫn là phản ứng sau impact. Static ReDoS checks, shadow evaluation và canary rollout có giá trị hơn việc chỉ hạ latency threshold.
3. RCA ở service level chưa đủ cho config-driven incident. Alert cần rule ID, pattern hash và deploy version để chỉ ra artifact thay đổi, không chỉ `edge-waf`.

## 1 thứ pipeline của tôi sẽ vẫn miss nếu outage này xảy ra real

- Pattern: một regex chỉ backtrack với input hiếm, trong khi canary traffic không chứa chuỗi kích hoạt.
- Why miss: p99 có thể chưa dịch chuyển nếu tỷ lệ adversarial request quá thấp; service vẫn trả HTTP 200 và CPU spike chỉ xuất hiện trên một subset worker.
- Mitigation idea: pre-deploy complexity analysis, fuzz corpus với worst-case strings, per-rule execution timing, và timeout/kill switch độc lập với aggregate SLI.

## 1 quyết định trong ADR mà tôi không hoàn toàn chắc

Tôi chưa chắc mọi WAF rule đều nên qua ba bước 1%-10%-100%. Security emergency rule cần triển khai nhanh để chặn active exploit; canary dài có thể giữ hệ thống dễ bị tấn công. Tôi sẽ cho phép expedited path nhưng vẫn bắt buộc static scan, bounded execution, shadow test ngắn và automatic rollback.

## Cost model verdict cho stack của tôi

- ROI: `2.0`
- Payback: `0.5` tháng
- Monthly value: `$36,000`
- Monthly cost: `$18,000`
- Verdict: `worth_it`

Kết quả phụ thuộc giả định GeekShop có 4 incident/tháng, mỗi incident 1.5 giờ, downtime `$15,000/hour` và pipeline giảm MTTR 40%. Nếu incident volume hoặc downtime cost thấp hơn một nửa, quyết định cần được tính lại.
