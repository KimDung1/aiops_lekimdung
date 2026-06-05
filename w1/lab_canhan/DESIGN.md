# Detection Approach - DESIGN.md

## Approach tôi dùng

Rule-based streaming detection với sliding window ngắn.

## Tại sao chọn approach này

Generator tạo ba loại sự cố có dấu hiệu rất rõ trên metric stream: memory leak, traffic spike, và dependency timeout. Vì bài lab cần pipeline chạy ổn định trong thời gian ngắn, rule-based detection phù hợp hơn mô hình học máy: dễ giải thích, không cần dữ liệu train trước, ít dependency, và có thể phát hiện ngay khi metric vượt ngưỡng.

## Cách hoạt động

Pipeline mở HTTP endpoint `POST /ingest`, đọc `metrics` và `logs` từ generator, sau đó phân loại tín hiệu bất thường ở từng tick. Để tránh alert giả do noise, pipeline chỉ fire alert khi cùng một loại fault xuất hiện ít nhất 2 lần trong 3 điểm dữ liệu gần nhất. Khi xác nhận anomaly, pipeline ghi một dòng JSON vào `alerts.jsonl` với `timestamp`, `type`, `severity`, và `message` chứa evidence chính.

## Parameters tôi chọn

- Window size: 12 điểm dữ liệu, đủ giữ context ngắn của stream nhưng không làm chậm phát hiện.
- Confirmation: 2 trong 3 điểm gần nhất, giúp giảm false alert nhưng vẫn phát hiện nhanh.
- Cooldown: 300 giây cho mỗi loại fault, tránh spam nhiều alert giống nhau.
- `memory_leak`: memory utilization >= 60% kèm GC pause >= 45ms, hoặc memory >= 75% kèm CPU cao, hoặc log `OutOfMemoryWarning`.
- `traffic_spike`: request/sec >= 300, queue depth >= 40, latency >= 200ms, và upstream timeout chưa cao. Điều kiện này tách traffic spike khỏi dependency timeout.
- `dependency_timeout`: upstream timeout rate >= 5% hoặc log timeout/circuit breaker, kèm latency >= 180ms.

## Cải thiện nếu có thêm thời gian

Tôi sẽ thêm adaptive baseline theo giờ trong ngày cho traffic, lưu state ra disk để restart không mất context, và xuất thêm metrics nội bộ của pipeline như số request đã ingest, số alert đã fire, và thời gian từ khi fault bắt đầu đến khi phát hiện.
