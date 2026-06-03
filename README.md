# aiops_lekimdung

AIOps Assignment — Lê Kim Dung

## Cấu trúc Repository

```
aiops_lekimdung/
├── w1/
│   ├── d1/                        ← Assignment ngày 1
│   │   ├── assignment.ipynb       # Notebook: Skewness, 3σ, EWMA, STL, iForest, Precision/Recall
│   │   ├── SUBMIT.md              # Nộp bài ngày 1
│   │   └── images/                # Ảnh viết tay knowledge check (5 trang)
│   │
│   ├── d2/                        ← Assignment ngày 2
│   │   ├── assignment.ipynb       # Notebook: Drain3 log parsing, anomaly detection
│   │   ├── SUBMIT.md              # Nộp bài ngày 2 (plots + logs + reflection)
│   │   └── images/                # Plots + drain output JSON + ảnh KC
│   │
│   └── d3/                        ← Assignment ngày 3
│       ├── pipeline.py            # Mock streaming pipeline + rolling features
│       ├── cost_model.py          # Cost estimate build vs buy
│       ├── architecture.md        # E2E observability data layer
│       ├── architecture.png       # Architecture diagram image
│       ├── generate_architecture_png.py # Script tạo architecture.png
│       ├── ADR-001.md             # Kafka vs direct push decision
│       ├── features.json          # Output từ pipeline.py
│       └── SUBMIT.md              # Nộp bài ngày 3
│
└── README.md
```

## Week 1 - Day 1 — AIOps Knowledge Check

1. Skewness & 3σ failure + 2 solutions
2. 3σ vs EWMA vs STL comparison
3. Isolation Forest path length & feature engineering
4. Univariate vs Multivariate (Memory Leak scenario)
5. Precision vs Recall in AIOps

## Week 1 - Day 2 — Log Parsing với Drain3

1. Drain3 parse tree — cách hoạt động
2. Log parsing vs grep — ví dụ cụ thể
3. Template count time series & anomaly detection
4. New template detection signal
5. Metric vs Log — kết hợp cho root cause analysis

## Week 1 - Day 3 — Data Layer Architecture + Observability Pipeline

1. Three pillars of observability: metric, log, trace
2. Mock streaming pipeline: producer → queue → consumer → features
3. E2E architecture cho payment service anomaly detection
4. Cost model cho Small / Medium / Large scale
5. ADR: chọn Kafka thay direct push
