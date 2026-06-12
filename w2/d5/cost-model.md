# A3. Cost Model

## Tóm tắt

Mục tiêu đề bài: giảm ít nhất **40%** chi phí observability trong 6 tháng.

Thiết kế target giảm từ khoảng **42.000 USD/tháng** xuống khoảng **10.079 USD/tháng**.

```text
Current monthly cost = 42.000 USD
Target monthly cost  = 10.079 USD
Monthly saving       = 31.921 USD
Reduction            = 31.921 / 42.000 = 76,0%
```

Thiết kế vượt yêu cầu 40% cost reduction, đồng thời giữ metrics/logs/traces và cải thiện alert correlation.

## Cost model hiện tại

Nguồn: `current-stack.md`.

| Line item hiện tại | Vendor/tool | Unit cost driver | Scale hiện tại | Chi phí/tháng |
|---|---|---|---:|---:|
| APM hosts | Datadog Pro | 40 USD/host/tháng | 295 host equivalents | 11.800 USD |
| Infrastructure metrics | Datadog Pro | 18 USD/host/tháng | 300 hosts | 5.400 USD |
| Custom metrics overage | Datadog | 5 USD / 100 active series vượt quota | khoảng 440k excess active series | 2.200 USD |
| Indexed logs | Datadog Logs | 1,70 USD / triệu event indexed | khoảng 1,05B event/tháng | 1.800 USD |
| Log storage + search | Splunk Cloud | workload + ingest | khoảng 52GB/ngày, 30 ngày retention | 13.900 USD |
| Incident routing + paging | PagerDuty Business | 60 USD/user/tháng | 65 active users | 3.900 USD |
| Dashboard mirror | Grafana Cloud Pro | active users | 12 viewers, 6 editors | 1.050 USD |
| Status page | Statuspage | tier subscription | Business tier | 290 USD |
| Synthetic checks | Datadog Synthetics | 5 USD/API check/tháng | khoảng 270 checks | 1.360 USD |
| Tracing premium tier | Datadog APM Pro | add-on | fixed add-on | 300 USD |
| **Tổng hiện tại** |  |  |  | **42.000 USD** |

## Cost model target

Giả định chính:

- Số host/service workload giữ tương đương hiện tại: khoảng 300 host equivalents.
- Hot log ingest giảm 50%: từ 52GB/ngày xuống 26GB/ngày nhờ structured logging, sampling và loại bỏ debug/noisy logs khỏi hot tier.
- Cold audit logs vẫn được giữ trong S3 90-180 ngày.
- Critical path như payment/checkout/edge giữ high-value traces bằng tail sampling.
- `customer_id` và các label high-cardinality bị drop hoặc hash trước khi ingest.

| Line item target | Component | Unit cost driver | Assumed scale | Chi phí/tháng |
|---|---|---|---:|---:|
| OpenTelemetry Collector | OSS/self-operated | compute/ops overhead | daemonset/collector trên cluster hiện có | 300 USD |
| Application observability base | Grafana Cloud | host/service equivalent | khoảng 300 host equivalents | 5.400 USD |
| Extra active metrics series | Grafana Cloud Metrics/Mimir | active series | khoảng 150k active series sau khi giảm cardinality | 975 USD |
| Hot logs | Grafana Cloud Logs/Loki | GB ingested/retained | 26GB/ngày, 15-30 ngày hot | 429 USD |
| Distributed traces | Grafana Cloud Traces/Tempo | GB spans ingested/retained | tail sampled critical traces | 165 USD |
| Dashboards/users | Grafana | active users | 65 engineering/on-call users | 520 USD |
| Incident routing + paging | Grafana IRM | user seats | 65 users | 1.300 USD |
| Cold audit logs | S3 + Athena/OpenSearch ad-hoc | GB stored + query budget | 52GB/ngày raw logs, 90-180 ngày | 200 USD |
| Synthetic checks | Grafana/k6-style checks | checks/executions | critical endpoints only | 500 USD |
| Status page | Statuspage | tier subscription | giữ Business tier | 290 USD |
| **Tổng target** |  |  |  | **10.079 USD** |

## So sánh current vs target

| Capability | Current cost | Target cost | Thay đổi |
|---|---:|---:|---:|
| APM + infra metrics + custom metrics | 19.400 USD | 6.675 USD | -12.725 USD |
| Logs hot/indexed | 15.700 USD | 429 USD | -15.271 USD |
| Cold/audit logs | included trong Splunk | 200 USD | +200 USD |
| Paging/routing | 3.900 USD | 1.300 USD | -2.600 USD |
| Dashboards/users | 1.050 USD | 520 USD | -530 USD |
| Synthetic checks | 1.360 USD | 500 USD | -860 USD |
| Status page | 290 USD | 290 USD | 0 USD |
| Collector/self-operated overhead | 0 USD | 300 USD | +300 USD |
| **Tổng** | **42.000 USD** | **10.079 USD** | **-31.921 USD** |

## Sensitivity row: nếu data volume tăng nhanh gấp 2 lần

| Scenario | Điều gì tăng? | Chi phí bị ảnh hưởng | Budget risk | Cách kiểm soát |
|---|---|---:|---|---|
| Data volume tăng 2x nhanh hơn dự kiến | Hot logs tăng từ 26GB/ngày lên 52GB/ngày; trace volume tăng 2x; active series tăng nếu team thêm label mới | Target có thể tăng thêm khoảng 600-1.500 USD/tháng tùy log/trace/cardinality | Phần dễ phá budget nhất là **metrics cardinality**, không phải raw log storage | Bắt buộc cardinality budget theo service, denylist label như `customer_id`, log sampling mặc định, alert khi active series/service vượt ngưỡng |

## Vì sao cost giảm nhưng performance không giảm

Cost giảm chủ yếu vì bỏ overlap và chuyển đúng retention tier:

- Không trả Datadog host-based APM + infra metrics cho toàn bộ 300 hosts.
- Không giữ toàn bộ 52GB/ngày trong Splunk hot index.
- Không index mọi log ở hot tier nếu chỉ cần audit dài ngày.
- Không trả PagerDuty seat cost cao cho workflow chỉ routing.

Performance incident response vẫn giữ vì:

- Metrics vẫn có đầy đủ cho SLO, latency, error rate, saturation.
- Traces quan trọng được giữ tốt hơn random 1% nhờ tail sampling.
- Hot logs vẫn có trong Loki cho incident gần.
- Audit/security logs vẫn còn trong S3 cold tier.
- Alert correlation tốt hơn nhờ Grafana IRM.

## Nguồn pricing dùng để đối chiếu

- Grafana Cloud pricing public page: https://grafana.com/pricing/  
  Metrics Pro **6,50 USD / 1k active series**, Logs/Traces Pro **0,05 USD/GB process + 0,40 USD/GB write + 0,10 USD/GB retain**, Application Observability Pro **18 USD/host**, Grafana visualization **8 USD/active user**, IRM **20 USD/active IRM user**.
- AWS S3 pricing public page: https://aws.amazon.com/s3/pricing/  
  S3 tính phí theo storage class, dung lượng lưu, thời gian lưu, request và retrieval; cost model dùng S3 cold tier như ngân sách thấp cho raw audit logs thay vì hot-index toàn bộ log trong Splunk.
- Current-state pricing lấy trực tiếp từ `current-stack.md` của đề bài.
