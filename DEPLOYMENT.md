# Deployment Guide & Verification — Day 14 (K5)

**Họ tên:** Nguyễn Lâm Tùng (MSSV: 2A202603854)  
**Platform:** Render (Docker Web Service + Render Key Value / Redis)  
**Public URL:** https://k5-l3b-day14-nguyenlamtung-2a202603854.onrender.com  
**Repository:** https://github.com/nlamtung/K5-L3B-DAY14-NguyenLamTung-2A202603854-Deployment-Benchmark-Observability

---

## 1. Kiến trúc Deploy

- **Web Service:** Docker container build từ `06-lab-complete/Dockerfile` (multi-stage `python:3.11-slim`, non-root user `appuser`, bind `0.0.0.0:$PORT`, healthcheck `/health`).
- **Redis (Render Key Value):** Lưu trạng thái rate limiter (sliding window) và cost guard (ngân sách ngày), kết nối nội bộ qua `REDIS_URL`.
- **Environment Variables (đặt trên Render Dashboard, không commit vào Git):**
  - `AGENT_API_KEY`: `<secret>`
  - `REDIS_URL`: `<Render Internal Redis URL>`
  - `RATE_LIMIT_PER_MIN`: `10` (mặc định)
  - `DAILY_BUDGET_USD`: `5.0` (mặc định)

---

## 2. Kết quả Self-Test trên Public URL

### 1. Liveness Probe (`GET /health` → 200)
```bash
curl -s https://k5-l3b-day14-nguyenlamtung-2a202603854.onrender.com/health
```
```json
{"status":"ok","environment":"development"}
```

### 2. Readiness Probe (`GET /ready` → 200, Redis connected)
```bash
curl -s https://k5-l3b-day14-nguyenlamtung-2a202603854.onrender.com/ready
```
```json
{"status":"ready","redis":"ok"}
```

### 3. Auth Check — Không có API Key (`POST /ask` → 401)
```bash
curl -i -X POST https://k5-l3b-day14-nguyenlamtung-2a202603854.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
```
Kết quả: `HTTP 401 Unauthorized` (từ chối request không có `X-API-Key`).

### 4. Authenticated Request (`POST /ask` với `X-API-Key` → 200)
```bash
curl -s -X POST https://k5-l3b-day14-nguyenlamtung-2a202603854.onrender.com/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <API_KEY>" \
  -d '{"question":"Docker la gi?"}'
```
Kết quả: `HTTP 200 OK` (trả về câu trả lời từ AI Agent).

---

## 3. Screenshots

- `screenshots/dashboard.png` — Render Dashboard hiển thị Web Service & Key Value (Redis)
- `screenshots/running.png` — Service trạng thái **Live** + logs khởi động
- `screenshots/test.png` — Kết quả `curl` kiểm thử `/health`, `/ready`, `/ask` (401 & 200)
