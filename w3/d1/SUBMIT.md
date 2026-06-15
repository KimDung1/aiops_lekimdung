# W3-D1 Submission - Le Kim Dung

## 3 thứ tôi học được

1. SLI phải đo user pain, không phải chỉ đo resource saturation. CPU hoặc memory có ích cho capacity nhưng không thể thay cho availability/latency SLI. Trong dữ liệu này API p99 chỉ `156ms`, dù một metric hạ tầng có thể dao động mà user vẫn không bị ảnh hưởng.
2. Error budget biến SLO thành một con số có thể dùng để quyết định. API target `99.9%` với `20,737,800` request/tháng cho phép khoảng `20,738` failures, tương đương khoảng `43` phút downtime toàn phần.
3. Multi-window multi-burn-rate giảm noise tốt hơn single-window. Validator cho thấy static baseline có `19 FP`, còn MWMBR có `0 FP` và vẫn giữ `0 FN`.

## 1 thứ vẫn chưa rõ

Tôi vẫn muốn hiểu rõ hơn cách chọn SLO khi baseline ngắn chứa nhiều incident. Baseline 3 ngày của API có system fail rate `0.3488%`, trong khi target tôi chọn là `99.9%`. Tôi chưa chắc nên giữ target mang tính định hướng hay cần một giai đoạn chuyển tiếp với SLO thấp hơn rồi tăng dần sau mỗi quý.

## 1 trade-off trong SLO decision của tôi mà tôi không chắc

Tôi chọn latency cutoff `500ms` vì p99 là `156ms`, p99.9 là `394ms`, và `99.94%` request dưới `500ms`. Trade-off là ngưỡng này giảm false positive nhưng có thể coi request `300-450ms` là good dù một số luồng checkout vẫn cảm thấy chậm. Ngưỡng `200ms` phản ánh trải nghiệm tốt hơn nhưng quá gần tail baseline và có thể đốt budget vì jitter không đáng page.

## Validation report

- noise_reduction_pct: 86.4%
- mttd_delta_s: 0s
- false_negative: 0
- static_false_positive: 19
- mwmbr_false_positive: 0
- verdict: pass
