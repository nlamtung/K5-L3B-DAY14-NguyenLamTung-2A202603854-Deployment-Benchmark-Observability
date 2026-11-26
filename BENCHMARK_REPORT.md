# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Nguyễn Lâm Tùng (MSSV: 2A202603854)
**Ngày chạy:** 2026-11-26
**Môi trường:** Windows 11 + WSL2 Ubuntu + Docker Desktop

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Đảm bảo 95% người dùng nhận được phản hồi nhanh, không bị cảm giác giật/treo khi tương tác với agent |
| Error rate `/ask` | < 2 % | Cho phép error budget nhỏ cho lỗi mạng/transient 503 nhưng vẫn giữ trải nghiệm ổn định (98%+ thành công) |
| Accuracy trên golden dataset | ≥ 100 % | Đảm bảo mọi câu hỏi chuẩn về kiến thức cốt lõi đều được trả lời đúng, không bị regression trước khi deploy |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.32 | 204.8 | 236.1 | 1707.7 | 0.00% | PASS |
| 10 | 37.33 | 204.4 | 480.7 | 1716.9 | 1.33% | PASS |
| 50 | 96.76 | 212.2 | 618.8 | 1749.6 | 0.33% | FAIL |
| 100 | 40.08 | 1077.5 | 5465.5 | 5766.6 | 0.67% | FAIL |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Không. Từ concurrency 1 → 10 → 50, RPS tăng từ 4.32 → 37.33 → 96.76 (đạt đỉnh ở 50), nhưng đến concurrency 100 thì RPS **giảm mạnh xuống 40.08** trong khi p50 tăng vọt lên 1077.5ms và p95 lên 5465.5ms. Nguyên nhân là do single-process uvicorn bị quá tải event loop / kết nối đồng thời (queuing delay), request phải xếp hàng chờ xử lý nên latency tăng phi tuyến và throughput sụt giảm.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 231.7 | 475.2 | 545.2 |
| 0.03 (mặc định) | 283.2 | 524.4 | 1695.7 |
| 0.1 | 395.3 | 1703.3 | 1724.2 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

- **p99** (và **p95** khi tỷ lệ chậm vượt 5%) nhạy nhất với request chậm: chỉ cần `MOCK_SLOW_RATE = 0.03` (3%), p99 đã nhảy vọt từ 545.2ms lên 1695.7ms (gấp >3 lần), còn khi lên `0.1` (10%) thì p95 nhảy lên 1703.3ms.
- **Không nên đặt SLO theo average** vì giá trị trung bình bị "làm mượt" bởi đa số request nhanh (khi 10% request chậm 1.7s, avg vẫn chỉ 395.3ms — trông có vẻ đạt chuẩn <500ms, nhưng thực tế 1/10 người dùng đang phải chờ gần 2 giây).

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 55.6 | 109.0 | 114.4 |
| Tổng cost (USD) | $0.000384 | $0.000760 | $0.000797 |
| Cost / câu đúng (USD) | $0.00038355 | $0.00003619 | $0.00003465 |
| Quality gate | FAIL | PASS (≥80%) | PASS (≥100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry giải thích JWT vs API key vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry giải thích Kubernetes HPA (Horizontal Pod Autoscaler) vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

Agent v2 (có RAG retrieval) tốn gần gấp đôi số token (109–114.4 vs 55.6) và tổng cost cao hơn (~$0.000797 vs $0.000384), latency p95 tương đương (~215–230ms vs 215ms). Tuy nhiên accuracy tăng vọt từ 4.35% lên 100%, giúp **cost trên mỗi câu trả lời đúng giảm hơn 11 lần** ($0.00003465 vs $0.00038355). Đây là trade-off cực kỳ xứng đáng trong production.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals) — `screenshots/grafana-dashboard.png`
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian) — `screenshots/jaeger-slow-trace.png`
- [x] Một trace lỗi trong Jaeger (có event `exception`) — `screenshots/jaeger-error-trace.png`
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing** — `screenshots/prometheus-alert-firing.png`

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `HighErrorRate` | ~30–45s | Error Rate (%) & HTTP Status Codes (5xx) |
| B | `MOCK_SLOW_RATE=0.3` | `HighLatencyP95` | ~30–45s | Latency p50 / p95 / p99 |
| C | `LLM_MODEL=mock-llm-large` | `HighLLMCostRate` (hoặc tăng đột biến cost) | ~30–60s | LLM Cost / Token Rate |
| D | `docker pause` 1 instance | `InstanceDown` (hoặc giảm `up` count) | ~15–30s | Active Instances / Traffic per Instance |
| E | `AGENT_VERSION=v1` | Không có alert nào firing | N/A | Không panel hạ tầng nào bất thường (latency/error vẫn xanh) |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Alert hạ tầng (latency, error rate, CPU) không thể phát hiện suy giảm chất lượng câu trả lời (quality regression). Để phát hiện trong production cần kết hợp:
1. **CI/CD Quality Gate**: chạy `eval/run_eval.py` trên golden dataset trước mỗi lần deploy (chặn deploy nếu accuracy giảm hoặc có regression).
2. **Online evaluation / LLM-as-a-Judge**: lấy mẫu (sampling) các câu trả lời thật trên production để chấm điểm tự động và export metric `agent_eval_accuracy` sang Prometheus.
3. **User feedback signals**: theo dõi tỷ lệ thumbs-down, retry rate, hoặc tỷ lệ fallback/escalation của người dùng.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `47f88296538632f87f586b9ffd8c512d`
- Tổng thời gian: `1669.0` ms
- Span chiếm nhiều thời gian nhất: `llm_call` (`1648.8` ms, `98.8%`)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-26T09:49:28.324280+00:00", "level": "INFO", "service": "observable-agent", "instance": "d995b386c5b8", "event": "llm_call", "trace_id": "47f88296538632f87f586b9ffd8c512d", "span_id": "cc829e6c2504122b", "request_id": "8c7d1fe79f7b", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 37, "output_tokens": 24, "cost_usd": 2e-05, "llm_ms": 1648.8}
{"ts": "2026-11-26T09:49:28.325134+00:00", "level": "INFO", "service": "observable-agent", "instance": "d995b386c5b8", "event": "http_request", "trace_id": "47f88296538632f87f586b9ffd8c512d", "span_id": "cc829e6c2504122b", "request_id": "8c7d1fe79f7b", "method": "POST", "route": "/ask", "status": 200, "ms": 1669.0}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 64.24 | 200 | 580 | 1700 | 75 (0.98%) |
| 3 | 66.05 | 190 | 240 | 1700 | 78 (0.99%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

- **Có cải thiện rõ rệt p95:** Khi scale từ 1 lên 3 instance, p95 giảm mạnh từ **580 ms → 240 ms** (giảm ~58.6%, đưa hệ thống từ vi phạm SLO >500ms về đạt SLO <500ms).
- **Vì sao RPS tăng ít (64.24 → 66.05) và p99 giữ nguyên (1700 ms)?**
  1. Ở `scale=1`, mỗi container bị giới hạn `0.5 CPU` nên 100 users gây nghẽn hàng đợi (queuing), đẩy p95 lên 580ms. Scale lên 3 instance giải tỏa nút thắt CPU/queuing này.
  2. Locust user có `wait_time` giữa các request nên tổng lượng tải tối đa từ 100 user quanh mức ~65 RPS.
  3. **p99 (1700 ms)** không giảm vì nút thắt nằm ở **upstream LLM latency** (`MOCK_SLOW_RATE=0.03` tạo độ trễ cố định ~1.6s cho 3% request). Scale ngang thêm container không thể làm giảm độ trễ của lời gọi LLM chậm — cần xử lý bằng timeout, caching, hoặc fallback model.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **Tail latency (p95/p99) quan trọng hơn average:** Average dễ che giấu trải nghiệm xấu của nhóm người dùng gặp request chậm; SLO phải đặt theo p95/p99.
  2. **Observability cần cả 3 trụ cột (Metrics + Traces + Structured Logs):** Metrics/Alerts báo có sự cố, Traces (Jaeger) chỉ rõ span nào chậm (`llm_call` chiếm 98.8%), còn JSON logs gắn `trace_id` giúp đối chiếu chi tiết request.
  3. **Hạ tầng xanh không đồng nghĩa chất lượng tốt:** Phải kết hợp eval trên golden dataset (CI quality gate) để bắt regression về độ chính xác và tối ưu cost/câu đúng.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

  - **Cost & Budget alerts:** `daily_llm_cost_usd` vượt 80%/100% ngân sách ngày, và `tokens_per_request` tăng bất thường (phát hiện prompt injection hoặc loop).
  - **Rate limit & Auth metrics:** Tỷ lệ HTTP 401/429 tăng đột biến (phát hiện brute-force hoặc abuse API key).
  - **Dependency health:** Redis latency / connection errors và LLM provider timeout/rate-limit (429 từ OpenAI/Anthropic).
