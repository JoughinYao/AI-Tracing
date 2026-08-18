# System API

本目录是系统后端。

## 本地开发

```bash
cd apps/api
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python -m uvicorn app.main:app --reload --port 8100
```

## 服务器部署

见 [../../deploy/server-linux.md](../../deploy/server-linux.md)

## 关键接口

- `GET /api/home/today`
- `GET /api/items?section=core-agent&date=2026-08-12&page=1&page_size=20`
- `GET /api/core-agent/metrics`
- `GET /api/system-logs`
- `GET /api/crawl-batches`
- `POST /api/crawl-batches/run`
