# W2-D1 Submit - Alert Correlation

## Kết quả chạy

- Input alerts: 20
- Output clusters: 3
- Reduction ratio: 0.85
- File kết quả: `results/cluster_summary.json`

## Design choices

Tôi chọn `gap_sec = 120` vì alert flood trong dataset là một burst liên tục quanh sự cố payment. Gap 2 phút đủ rộng để gom các alert lan truyền từ `payment-svc` sang `checkout-svc`, `edge-lb`, `cart-svc`, `notification-svc`, nhưng vẫn không quá rộng như 5-10 phút, vốn có thể gom nhầm nhiều incident độc lập. Với production thật, tôi sẽ chọn tham số này bằng histogram khoảng cách thời gian giữa các alert trong cùng incident.

Tôi chọn `max_hop = 1` vì topology trong dataset có nhiều service gần nhau qua `edge-lb` và `catalog-db`. Nếu dùng `max_hop = 2`, `recommender-svc` có thể bị kéo vào cluster chính thông qua `catalog-svc` hoặc `edge-lb`, dù note nói đây là batch retrain độc lập. `max_hop = 1` vẫn gom được cascade chính: `payment-svc` nối `checkout-svc`, `checkout-svc` nối `edge-lb`, `cart-svc`, `notification-svc`.

Alert bị miss/không match cluster chính là `a-0013` của `recommender-svc`. Alert này xảy ra cùng thời gian với payment incident, nhưng label note ghi rõ `unrelated - concurrent batch retrain`. Vì vậy tôi tách nó thành cluster singleton để on-call không nhầm batch retrain ML với payment outage. Alert `a-0016` của `search-svc` cũng tương tự: note ghi independent slow query.

Nếu có 10000 alert thay vì 20, code sẽ chậm ở phần tính shortest path giữa từng cặp service trong mỗi session. Với số service ít thì ổn, nhưng khi topology lớn hơn, cặp service là O(S²), mỗi lần lại BFS. Cách cải thiện là cache shortest path theo cặp service, precompute all-pairs shortest paths cho graph nhỏ/trung bình, hoặc dùng union theo neighborhood đã tính trước.

## EOD Checkpoint

### 1. Vì sao fingerprint không include timestamp hay value?

Fingerprint không nên include `timestamp` hoặc `value` vì hai field này thay đổi gần như mỗi lần alert fire. Ví dụ `payment-svc|latency_p99_ms|crit` xuất hiện ở `a-0003`, `a-0008`, `a-0015`; nếu thêm timestamp thì ba alert này thành ba fingerprint khác nhau và dedup mất tác dụng. Nếu thêm value, cùng một lỗi latency nhưng giá trị 1840ms, 1900ms, 2100ms cũng bị xem là ba loại alert khác nhau. Fingerprint nên dùng các field ổn định như service, metric, severity để nhận ra cùng một kiểu vấn đề đang lặp lại.

### 2. Duplicate và correlated alert khác nhau thế nào?

Duplicate alert là cùng một loại alert bắn nhiều lần, ví dụ `payment-svc|latency_p99_ms|crit` xuất hiện ở `a-0003`, `a-0008`, `a-0015`. Chúng có cùng service, metric, severity nên là một fingerprint lặp lại. Correlated alert rộng hơn: các alert khác fingerprint nhưng có liên quan trong cùng incident. Ví dụ `payment-svc` latency/error, `checkout-svc` downstream payment error, và `edge-lb` upstream 5xx khác metric nhưng cùng nằm trong cascade payment outage.

### 3. gap_sec = 30 vs gap_sec = 600 ảnh hưởng output thế nào?

`gap_sec = 30` sẽ tách incident chính thành nhiều session nhỏ vì có các khoảng cách trên 30 giây, ví dụ từ `a-0012` đến `a-0013` là 40 giây.

`gap_sec = 600` sẽ gom gần như toàn bộ alert trong 10 phút vào cùng session, tăng nguy cơ merge nhầm incident độc lập nếu không có topology/noise filter.

### 4. Recommender-svc có bị gom vào cluster chính không?

Không. Correlator của tôi tách `recommender-svc` thành cluster riêng vì alert `a-0013` có note `unrelated - concurrent batch retrain`. Đây là điểm quan trọng: time-window alone sẽ gom nhầm vì alert xảy ra ngay giữa payment incident. Topology max_hop quá rộng cũng có thể kéo nó vào qua catalog path. Vì vậy tôi dùng `max_hop = 1` và rule tách singleton cho alert được đánh dấu unrelated/noise/independent.

### 5. Limitation lớn nhất của topology grouping là gì?

Limitation lớn nhất là topology chỉ biết service nào nối với service nào, nhưng không biết hướng lan truyền thật, traffic volume, retry behavior, hay trạng thái runtime lúc đó. Hai service gần nhau trên graph chưa chắc cùng root cause. Cách khắc phục là kết hợp thêm metric evidence, dependency direction, trace/span error, log semantic similarity, và dynamic edge weight dựa trên traffic thực tế trong vài phút quanh incident.
