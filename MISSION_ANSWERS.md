# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns trong `01-localhost-vs-production/develop/app.py`

1. **Hardcode secrets trong source code** (dòng 17–18): `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`. Nếu push lên GitHub (đặc biệt repo public), key và mật khẩu DB bị lộ ngay lập tức.
2. **In secret ra log bằng `print()`** (dòng 33–34, 38): `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` vừa làm rò rỉ API key vào stdout/log, vừa dùng `print()` tự do thay vì structured logging nên khó tìm kiếm/phân tích.
3. **Cấu hình cố định trong code, không đọc từ biến môi trường** (dòng 21–22, 51–53): `DEBUG = True`, `MAX_TOKENS = 500`, `host="localhost"`, `port=8000`, `reload=True`. Trên cloud (Railway/Render) hoặc trong Docker, nền tảng cấp `PORT` động và cần bind `0.0.0.0` chứ không phải `localhost`.
4. **Bật `reload=True` (debug mode) khi chạy server** (dòng 53): Theo dõi thay đổi file tốn tài nguyên, không an toàn và không phù hợp cho production.
5. **Không có health check / readiness endpoint** (không có `/health`, `/ready`): Platform/Load Balancer không biết container còn sống hay đã sẵn sàng nhận traffic để tự động restart hoặc điều hướng.
6. **Không xử lý graceful shutdown** (không có `lifespan` hay xử lý `SIGTERM`): Khi platform tắt hoặc deploy bản mới, server bị ngắt đột ngột, dễ cắt ngang request đang xử lý.

### Exercise 1.2: Kết quả chạy bản `develop`

Lệnh gọi (`POST /ask?question=Hello`):

```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:29:21 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

### Exercise 1.3: So sánh `develop/app.py` vs `production/app.py`

Kết quả kiểm tra bản `production`:
- `GET /health` → `200 OK`: `{"status":"ok","uptime_seconds":2.4,"version":"1.0.0","environment":"development","timestamp":"2026-11-26T07:29:26.106199+00:00"}`
- `POST /ask` (body JSON `{"question":"Hello"}`) → `200 OK`: `{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","model":"gpt-4o-mini"}`

| Feature | Develop (`develop/app.py`) | Production (`production/app.py`) | Tại sao quan trọng? |
| --- | --- | --- | --- |
| **Config & Secrets** | Hardcode `OPENAI_API_KEY`, `DATABASE_URL`, `port=8000`, `host="localhost"` (dòng 17–18, 51–52) | Đọc qua `settings` từ biến môi trường / `.env`, bind `0.0.0.0` và `PORT` động (dòng 24, 196–198) | Không lộ secret lên Git; cùng một code chạy được ở dev/staging/prod mà không cần sửa code. |
| **Health check** | Không có endpoint kiểm tra sức khỏe | Có `GET /health` (liveness) và `GET /ready` (readiness, trả 503 khi chưa sẵn sàng) (dòng 135–161) | Platform biết khi nào cần restart container hỏng (`/health`) và Load Balancer biết khi nào mới được gửi traffic vào (`/ready`). |
| **Logging** | Dùng `print("[DEBUG] ...")`, in cả `OPENAI_API_KEY` (dòng 33–38) | Dùng `logging` với format JSON, chỉ log metadata (`event`, `question_length`, `client_ip`), không log secret (dòng 28–32, 111–122) | Structured JSON log giúp các hệ thống như Loki/Datadog lọc và cảnh báo tự động, đồng thời tránh lộ dữ liệu nhạy cảm. |
| **Shutdown** | Thoát đột ngột khi nhận tín hiệu dừng | Dùng `lifespan` (`is_ready = False`, chờ request hoàn thành) và đăng ký `signal.SIGTERM` (dòng 39–67, 180–189) | Không làm rớt request của người dùng đang xử lý dở khi rolling deploy hoặc restart container. |
| **CORS & Input** | Không cấu hình CORS; nhận `question` qua query param | Cấu hình `CORSMiddleware` theo `allowed_origins` và nhận JSON body có kiểm tra lỗi `422` (dòng 77–82, 102–108) | Kiểm soát domain được phép gọi API và chuẩn hóa contract dữ liệu đầu vào. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile cơ bản (`02-docker/develop/Dockerfile`)

1. **Base image:** `python:3.11` (bản đầy đủ gồm Debian OS + Python 3.11 + công cụ build, dung lượng lớn).
2. **Working directory:** `/app` (`WORKDIR /app` — thư mục làm việc mặc định bên trong container).
3. **Tại sao `COPY requirements.txt` trước `COPY . .`?** Docker build theo từng layer và có cơ chế cache. Khi tách `COPY requirements.txt` + `RUN pip install` lên trước phần copy source code, nếu chỉ sửa code (`app.py`) mà không đổi `requirements.txt`, Docker tái sử dụng lại layer đã cài thư viện nên build rất nhanh.
4. **Khác nhau giữa `CMD` và `ENTRYPOINT`:** `CMD` định nghĩa lệnh/tham số mặc định và **dễ bị ghi đè** khi truyền tham số lúc `docker run <image> <cmd_mới>`; còn `ENTRYPOINT` cố định file thực thi chính (tham số truyền thêm lúc `docker run` sẽ nối vào sau `ENTRYPOINT`).

### Exercise 2.2: Build và chạy container bản `develop`

Lệnh build từ gốc repo: `docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .`  
Kết quả gọi `POST http://localhost:8000/ask?question=What_is_Docker`:

```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 08:09:22 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### Exercise 2.3: Multi-stage build & So sánh dung lượng image

- **Stage 1 (`builder`):** Dùng `python:3.11-slim`, cài `gcc` và `libpq-dev` để compile dependencies, cài package Python vào `/root/.local` bằng `pip install --user`.
- **Stage 2 (`runtime`):** Dùng lại base `python:3.11-slim` sạch sẽ, chỉ `COPY --from=builder /root/.local` sang `/home/appuser/.local`, copy source code, tạo user non-root `appuser`, khai báo `HEALTHCHECK` và chạy `uvicorn`. Không mang theo `gcc`, `apt` cache hay build tools nên image nhẹ hơn và an toàn hơn.
- **Kích thước đo thực tế bằng `docker images my-agent`:**
  - `my-agent:develop`: **1.67 GB** (~1,670 MB)
  - `my-agent:advanced`: **240 MB**
  - **Chênh lệch:** Giảm **85.6%** dung lượng (nhỏ hơn ~1,430 MB).

### Exercise 2.4: Docker Compose stack (`02-docker/production/docker-compose.yml`)

- **Các service chạy trong stack:** `agent` (FastAPI), `redis` (`redis:7-alpine`), `qdrant` (`qdrant/qdrant:v1.9.0`), `nginx` (`nginx:alpine`).
- **Sơ đồ kiến trúc (giao tiếp qua Docker network nội bộ `internal`):**

```text
Client (localhost:80)
   │
   ▼
Nginx (reverse proxy, port 80/443)
   │
   ▼
Agent (FastAPI, port 8000, depends_on redis + qdrant)
   ├──► Redis (port 6379 — session cache & rate limiting)
   └──► Qdrant (port 6333 — vector database)
```

- **Kết quả test qua Nginx:**
  - `GET http://localhost/health` → `200 OK`: `{"status":"ok","uptime_seconds":14.2,"version":"2.0.0","timestamp":"2026-11-26T08:10:08.986539"}`
  - `POST http://localhost/ask` → `200 OK`: `{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}`

---

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Deploy Agent Part 6 lên Cloud & So sánh `railway.toml` vs `render.yaml`

- **Public URL:** https://k5-l3b-day14-nguyenlamtung-2a202603854.onrender.com
- **Platform:** Render (Docker Web Service + Render Key Value / Redis)
- **Screenshots:** `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`

**So sánh `railway.toml` vs `render.yaml`:**
- **Phạm vi cấu hình:** `railway.toml` cấu hình cho **1 service** (`[build] builder = "DOCKERFILE"`, `[deploy] healthcheckPath = "/health"`, `restartPolicyType`), còn biến môi trường và Redis thường thêm trên Dashboard/CLI. Ngược lại, `render.yaml` là **Blueprint (Infrastructure as Code)** khai báo danh sách `services` (có thể khai báo cả web service lẫn `envVars` ngay trong file).
- **Quản lý secret:** `railway.toml` không chứa phần khai báo `envVars` (secret được set qua `railway variables set` hoặc Dashboard). `render.yaml` khai báo biến môi trường trực tiếp nhưng bắt buộc dùng `generateValue: true` (tự sinh secret) hoặc `sync: false` (nhập tay trên Dashboard) để không lộ secret trong Git.
- **Lý do khác nhau:** Railway tối ưu trải nghiệm CLI/auto-detect theo từng service đơn lẻ, trong khi Render Blueprint thiết kế để đồng bộ toàn bộ stack từ một file YAML trên GitHub.

### Exercise 3.3: GCP Cloud Run CI/CD (`03-cloud-deployment/production-cloud-run/`)

Dựa trên `cloudbuild.yaml` và `service.yaml`, pipeline CI/CD tự động chạy qua 4 bước tuần tự khi push lên nhánh `main`:
1. **`test`:** Dùng `python:3.11-slim` cài `requirements.txt` + `pytest` và chạy `pytest tests/ -v`.
2. **`build`:** Build Docker image gắn tag `$COMMIT_SHA` và `latest` (tận dụng `--cache-from` từ bản `latest`).
3. **`push`:** Đẩy image lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **`deploy`:** Gọi `gcloud run deploy ai-agent` lên vùng `asia-southeast1` (autoscale `1–10` instances, `512Mi` RAM, `1` CPU, lấy secret từ Secret Manager), kết hợp `livenessProbe` (`/health`) và `startupProbe` (`/ready`) định nghĩa trong `service.yaml`.

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (`04-api-gateway/develop/app.py`)

- **API key được check ở đâu?** Trong hàm dependency `verify_api_key` (dòng 39–54), đọc header `X-API-Key` qua `APIKeyHeader(name="X-API-Key", auto_error=False)` và inject vào endpoint `POST /ask` bằng `Depends(verify_api_key)`.
- **Khi thiếu / sai key:** Thiếu key trả về `401 Unauthorized`; sai key trả về `403 Forbidden`.
- **Cách rotate key:** Không hardcode key trong code mà đọc từ biến môi trường `AGENT_API_KEY`. Khi rotate, cập nhật biến môi trường trên server/platform (hỗ trợ danh sách key cũ + mới trong giai đoạn chuyển tiếp rồi thu hồi key cũ).

**Kết quả test bản `develop` (`AGENT_API_KEY=secret-key-123`):**

1. Không có key → **401**:
```http
HTTP/1.1 401 Unauthorized
date: Thu, 26 Nov 2026 07:51:26 GMT
server: uvicorn
content-length: 67
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

2. Có header `X-API-Key: secret-key-123` → **200**:
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:51:26 GMT
server: uvicorn
content-length: 145
content-type: application/json

{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

### Exercise 4.2 & 4.3: JWT Authentication & Rate Limiting (`04-api-gateway/production/`)

- **Thuật toán rate limit:** `Sliding Window Counter` trong `rate_limiter.py` (lưu timestamp các request trong `deque` theo `user_id`, loại bỏ timestamp cũ hơn `window_seconds = 60`).
- **Giới hạn:** User thường (`student`): **10 requests/phút** (`rate_limiter_user`); Admin: **100 requests/phút** (`rate_limiter_admin`). Phân biệt dựa vào `role` giải mã từ JWT token.

**Kết quả test bản `production` (lấy token tại `POST /auth/token` với `student` / `demo123`, đã che token):**

1. Không có JWT token → **401**:
```http
HTTP/1.1 401 Unauthorized
date: Thu, 26 Nov 2026 07:52:15 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 76
content-type: application/json

{"detail":"Authentication required. Include: Authorization: Bearer <token>"}
```

2. Có `Authorization: Bearer <MASKED_TOKEN>` → **200**:
```http
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 07:52:15 GMT
server: uvicorn
content-length: 184
content-type: application/json

{"question":"JWT","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.8e-05}}
```

3. Vòng lặp 11 request liên tiếp → Request 1..10 trả `200`, Request 11 trả **429**:
```http
HTTP/1.1 429 Too Many Requests
date: Thu, 26 Nov 2026 07:52:46 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795679627
retry-after: 59
content-length: 98
content-type: application/json

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4: Cost Guard (`04-api-gateway/production/cost_guard.py`)

- **Vai trò:** Rate limit chỉ giới hạn *tốc độ* gọi (số request/phút), còn Cost Guard bảo vệ *ngân sách tiền* (dựa trên token tiêu thụ thực tế hoặc ngân sách ngày/tháng) để tránh hóa đơn LLM tăng đột biến.
- **Cách hoạt động trong `cost_guard.py`:**
  1. Trước khi gọi LLM, gọi `check_budget(user_id)`: kiểm tra tổng chi phí hệ thống (`global_daily_budget_usd`) và chi phí từng user (`daily_budget_usd`); nếu vượt ngưỡng user → trả **`402 Payment Required`**, nếu gần ngưỡng (`warn_at_pct = 0.8`) → ghi log cảnh báo.
  2. Sau khi gọi LLM, gọi `record_usage(user_id, input_tokens, output_tokens)`: tính tiền theo đơn giá token và cộng dồn vào bộ đếm.
  3. Trong production (như Part 6), bộ đếm chi phí phải lưu trong **Redis** (với key theo ngày/tháng và `EXPIRE`) thay vì biến RAM để không bị mất khi restart hoặc chạy nhiều instance.

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Liveness (`/health`) vs Readiness (`/ready`)

- **`/health` (Liveness probe):** Kiểm tra process còn sống không. Luôn trả `200` khi ứng dụng còn chạy, **kể cả khi Redis tạm mất kết nối**, để tránh orchestrator restart container liên tục khi lỗi nằm ở dependency bên ngoài.
- **`/ready` (Readiness probe):** Kiểm tra ứng dụng đã sẵn sàng nhận traffic chưa (ping Redis/DB). Nếu mất kết nối Redis → trả **`503 Service Unavailable`** để Load Balancer tạm ngừng gửi request vào instance đó.

### Exercise 5.2: Graceful Shutdown (`SIGTERM`)

- Khi nhận `SIGTERM` (lúc `docker stop` hoặc deploy bản mới), server ngừng nhận kết nối mới, hoàn thành các request đang xử lý dở (in-flight), đóng kết nối Redis/DB rồi thoát với `exit code 0`, tránh làm lỗi request của người dùng.

### Exercise 5.3–5.5: Stateless Design & Scale 3 Instances với Redis + Nginx

- **Vì sao state trong RAM hỏng khi chạy nhiều instance?** Nếu lưu `conversation_history` hoặc bộ đếm rate limit trong biến RAM của từng instance, Load Balancer (Nginx) chia request sang instance khác nhau sẽ làm mất lịch sử hội thoại và lệch bộ đếm. Giải pháp là đưa toàn bộ state dùng chung sang **Redis**.
- **Kết quả chạy stack `05-scaling-reliability/production/` (`docker compose -p k5-day14-scaling up -d --build --scale agent=3` + `python test_stateless.py`):**
  - 3 instance agent (`instance-a0e981`, `instance-e48aa0`, `instance-1ef984`), `redis` và `nginx` (cổng `8080`) đều chạy healthy.
  - 5 request trong cùng session `e4261ce4-e7f5-4e3c-aefe-68ed7ffe510c` được Nginx phân phối qua cả **3 instance khác nhau**, nhưng truy vấn `GET /chat/{session_id}/history` vẫn trả về đủ **10 messages** (5 user + 5 assistant) nhờ lưu tập trung trong Redis.

---

## Part 6: Final Project (`06-lab-complete/`)

Kết quả chạy `python3 check_production_ready.py` trong Ubuntu WSL2 (có Docker):

```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

- Kích thước Docker image thực tế: **238 MB** (< 500 MB).
- Thời gian `docker stop`: **0.6s**, exit code **0**.

---

## AI log

- **CP1:** Dùng AI hướng dẫn kiểm tra môi trường, chạy thử `01-localhost-vs-production/develop/app.py` và `01-localhost-vs-production/production/app.py`, đối chiếu các anti-pattern và tổng hợp bảng so sánh vào `MISSION_ANSWERS.md`. Đã kiểm tra lại số dòng code và kết quả `curl` thực tế.
- **CP3 (Part 4):** Dùng AI hỗ trợ chạy kiểm thử `04-api-gateway/develop` và `04-api-gateway/production` (API Key 401/200, JWT `/auth/token`, vòng lặp rate limit 429) và tổng hợp giải thích Cost Guard vào `MISSION_ANSWERS.md`. Đã kiểm tra lại output HTTP thực tế và che token trước khi lưu.
- **CP2 (Part 2):** Dùng AI hướng dẫn build `my-agent:develop` và `my-agent:advanced`, chạy container và stack Docker Compose qua Nginx. Đã tự đối chiếu kích thước image (`1.67 GB` vs `240 MB`) và kết quả test thực tế.
- **CP4 (Part 5):** Dùng AI hỗ trợ chạy stack 3 instance với `-p k5-day14-scaling` và `test_stateless.py`, giải thích `/health` vs `/ready`, graceful shutdown và stateless Redis. Đã kiểm tra lại output thực tế từ 3 instance.
- **CP5 (Part 6):** Dùng AI hỗ trợ hoàn thiện các `TODO` trong `06-lab-complete/` (`config.py`, `auth.py`, `redis_client.py`, `rate_limiter.py`, `cost_guard.py`, `main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml`) và chạy kiểm thử trong Ubuntu WSL2 với Docker đạt `PASS 12/12 (43/43 checks passed)`. Đã kiểm tra lại từng tiêu chí trên kết quả thực tế.
