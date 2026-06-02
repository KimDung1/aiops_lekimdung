# SUBMIT.md — AIOps Knowledge Check

**Họ và tên:** Lê Kim Dung  
**Ngày nộp:** 01/06/2026  
**Repository:** https://github.com/KimDung1/aiops_lekimdung

---

## 📁 Nội dung nộp

| File | Mô tả |
|------|-------|
| `assignment.ipynb` | Notebook chứa toàn bộ phân tích, code minh họa và giải thích chi tiết 5 câu hỏi Knowledge Check |
| `SUBMIT.md` | File này — tóm tắt thông tin nộp bài |
| `images/knowledge_check_page1.png` | Ảnh viết tay — Câu 1: Skewness & 3σ |
| `images/knowledge_check_page2.png` | Ảnh viết tay — Câu 2: So sánh 3σ vs EWMA vs STL |
| `images/knowledge_check_page3.png` | Ảnh viết tay — Câu 3: Isolation Forest |
| `images/knowledge_check_page4.png` | Ảnh viết tay — Câu 4: Univariate vs Multivariate |
| `images/knowledge_check_page5.png` | Ảnh viết tay — Câu 5: Precision vs Recall |

---

## 📝 Tóm tắt Knowledge Check

### Câu 1 — Skewness & 3σ
- **Skewness** là độ lệch của phân phối dữ liệu so với phân phối chuẩn (right/left skew)
- **3σ sai** vì giả định Normal Distribution → với data skewed, threshold bị lệch, gây FP cao ở đuôi ngắn và miss anomaly ở đuôi dài
- **Xử lý:** (1) Log transformation, (2) Dùng Median + IQR thay mean/std

### Câu 2 — 3σ vs EWMA vs STL
| Method | Detect | Fail khi | Dùng khi |
|--------|--------|----------|----------|
| 3σ | Point anomaly | Data skewed/seasonal | Stable, normal dist |
| EWMA | Gradual drift | Sudden spike | Slow trend shift |
| STL | Seasonal anomaly | No clear seasonality | Clear periodic pattern |

### Câu 3 — Isolation Forest
- **Ý tưởng:** Anomaly ít điểm giống xung quanh → bị isolate nhanh → **path length ngắn**
- **Feature engineering cần thiết vì:** curse of dimensionality, scale khác nhau, time-series cần lag features, correlated features gây nhiễu

### Câu 4 — Univariate vs Multivariate (Memory Leak)
- **Univariate miss:** Mỗi metric (memory 85%, CPU 65%, latency 200ms) đều trong ngưỡng → không alert
- **Multivariate catch:** Phát hiện pattern Memory↑ + CPU↑ + GC↑ + Latency↑ đồng thời → điểm bất thường trong không gian nhiều chiều

### Câu 5 — Precision vs Recall
- **AIOps ưu tiên Recall** vì FN (miss anomaly) cost >> FP (false alert) cost
- **Trade-off:** Threshold thấp → Recall↑, Precision↓ (alert fatigue); Threshold cao → Precision↑, Recall↓ (miss incidents)
- **Giải pháp:** F2-score, alert deduplication, priority scoring

---

## ✅ Checklist nộp bài

- [x] `assignment.ipynb` — hoàn chỉnh với code và phân tích
- [x] `SUBMIT.md` — file này
- [x] Ảnh knowledge check viết tay — 5 trang (images/)
- [x] Push lên GitHub trước cuối ngày 01/06/2026
