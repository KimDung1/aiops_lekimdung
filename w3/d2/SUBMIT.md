# W3-D2 Submission - Le Kim Dung

## 3 thứ tôi học được về AIOps pipeline của mình

1. Detection tốt không đồng nghĩa RCA tốt. DNS latency được phát hiện sau `55s`, nhưng RCA chọn `api-gateway` vì graph không có node DNS.
2. External probe và internal metrics trả lời hai câu hỏi khác nhau. Log collector disk fill không làm user probe giảm, nhưng vẫn là failure nghiêm trọng vì pipeline mất telemetry.
3. Topology + temporal scoring tránh được bẫy “service ồn nhất là root”. Trong retry storm, checkout phát nhiều alert nhất nhưng RCA vẫn chọn payment và đáp ứng negative ground truth `NOT checkout-svc`.

## 1 fault mà tôi mong pipeline catch nhưng nó miss

- Experiment: `auth_clock_skew` (#6)
- Why I expected detection: clock lệch `+60s` làm JWT validation failures và probe pass-rate giảm từ steady-state `100%` xuống `96%`.
- Why pipeline missed (hypothesis): generic 5xx detector xem aggregate traffic nên lỗi trên 1 instance/25% traffic chìm dưới threshold. Pipeline thiếu auth-success SLI và clock-offset telemetry.

## 1 trade-off trong design pipeline mà tôi muốn rethink

Tôi muốn xem lại việc chỉ giữ application services trong topology. Graph gọn giúp correlation/RCA nhanh và ít false link, nhưng bỏ DNS, log collector, queue hoặc sidecar khiến RCA dừng ở symptom đầu tiên nhìn thấy. Tôi sẽ thêm infrastructure nodes có type/criticality và chỉ activate edge khi có runtime evidence, thay vì mở rộng graph tĩnh vô điều kiện.

## Scoreboard summary

- execution_mode: deterministic simulation (starter pack không có Docker stack/Pumba/Toxiproxy)
- detected: 8/10
- rca_correct: 7/8
- precision: 0.889
- recall: 0.800
- mttd_p50: 26s
- mttd_p95: 55s
- false_alarms: 1
- verdict: pass against assignment thresholds; real-stack validation still required
