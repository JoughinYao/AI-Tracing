# System API

运行：

```bash
D:\AI-Tracing\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

关键接口：

- `GET /api/home/today`
- `GET /api/items?section=core-agent&date=2026-08-12&page=1&page_size=20`
- `GET /api/core-agent/metrics`
- `GET /api/system-logs`
- `GET /api/crawl-batches`
- `POST /api/crawl-batches/run`
