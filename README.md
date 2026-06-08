# aiops_lekimdung

AIOps Assignment - Le Kim Dung

## Cấu trúc Repository

```text
aiops_lekimdung/
├── w1/
│   ├── d1/                              # Assignment ngày 1
│   │   ├── assignment.ipynb             # Notebook: Skewness, 3σ, EWMA, STL, iForest, Precision/Recall
│   │   ├── SUBMIT.md                    # Nộp bài ngày 1
│   │   └── images/                      # Ảnh viết tay knowledge check
│   │
│   ├── d2/                              # Assignment ngày 2
│   │   ├── assignment.ipynb             # Notebook: Drain3 log parsing, anomaly detection
│   │   ├── SUBMIT.md                    # Nộp bài ngày 2
│   │   └── images/                      # Plots, drain output JSON, ảnh knowledge check
│   │
│   ├── d3/                              # Assignment ngày 3
│   │   ├── pipeline.py                  # Mock streaming pipeline + rolling features
│   │   ├── cost_model.py                # Cost estimate build vs buy
│   │   ├── architecture.md              # E2E observability data layer
│   │   ├── architecture.png             # Architecture diagram image
│   │   ├── generate_architecture_png.py # Script tạo architecture.png
│   │   ├── ADR-001.md                   # Kafka vs direct push decision
│   │   ├── features.json                # Output từ pipeline.py
│   │   └── SUBMIT.md                    # Nộp bài ngày 3
│   │
│   └── lab_canhan/                      # W1 Individual Lab - Streaming Anomaly Pipeline
│       ├── pipeline.py                  # HTTP endpoint /ingest + anomaly detection
│       ├── stream_generator.py          # Generator gửi metrics/logs vào pipeline
│       ├── alerts.jsonl                 # Output alert JSONL
│       ├── DESIGN.md                    # Giải thích detection approach
│       ├── requirements.txt             # Dependencies
│       └── W1-individual-lab.md         # Đề bài lab cá nhân
│
├── w2/
│   └── d1/                              # Alert Correlation - từ noise sang signal
│       ├── assignment.ipynb             # Notebook chạy correlation pipeline
│       ├── correlate.py                 # Session window + topology-aware correlator
│       ├── SUBMIT.md                    # Reflection và EOD checkpoint
│       ├── dataset/
│       │   ├── alerts_sample.jsonl      # 20 alert đầu vào
│       │   └── services.json            # Service topology GeekShop
│       └── results/
│           └── cluster_summary.json     # Output cluster summary
│
└── README.md
```

## Week 1 - Day 1 - AIOps Knowledge Check

1. Skewness & 3σ failure + 2 solutions
2. 3σ vs EWMA vs STL comparison
3. Isolation Forest path length & feature engineering
4. Univariate vs Multivariate (Memory Leak scenario)
5. Precision vs Recall in AIOps

## Week 1 - Day 2 - Log Parsing với Drain3

1. Drain3 parse tree - cách hoạt động
2. Log parsing vs grep - ví dụ cụ thể
3. Template count time series & anomaly detection
4. New template detection signal
5. Metric vs Log - kết hợp cho root cause analysis

## Week 1 - Day 3 - Data Layer Architecture + Observability Pipeline

1. Three pillars of observability: metric, log, trace
2. Mock streaming pipeline: producer → queue → consumer → features
3. E2E architecture cho payment service anomaly detection
4. Cost model cho Small / Medium / Large scale
5. ADR: chọn Kafka thay direct push

## Week 1 - Individual Lab - Streaming Anomaly Pipeline

1. HTTP endpoint `POST /ingest` nhận stream metrics/logs từ generator
2. Rule-based anomaly detection cho `memory_leak`, `traffic_spike`, `dependency_timeout`
3. Ghi alert ra `alerts.jsonl` theo định dạng JSON Lines
4. `DESIGN.md` mô tả approach, thresholds, sliding window và cooldown

## Week 2 - Day 1 - Alert Correlation

1. Dedup bằng fingerprint `service|metric|severity`
2. Session window với `gap_sec = 120`
3. Topology-aware grouping với `max_hop = 1`
4. Output `results/cluster_summary.json`: 20 alert → 3 cluster, reduction ratio 0.85
