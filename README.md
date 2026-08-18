# AI Tracing

公司内部 AI 技术每日动态系统。第一阶段跑通采集、保存、展示、分类浏览、日期筛选、分页、日志查看主链路。

## 目录

- `apps/api`: 系统后端，FastAPI，端口 `8000`
- `apps/web`: 前端，Vue 3 + Vite，端口 `5173`
- `docs`: 产品、接口、部署文档
- `scripts`: 开发启动脚本
- `deploy`: 部署配置

## 本地运行

```powershell
.\scripts\run-api.ps1
.\scripts\run-web.ps1
```

爬虫后端作为独立服务，由系统后端调用，默认地址 `http://127.0.0.1:8001`。爬虫不可用时，后端会记录 fallback 日志并保持页面可访问；生产环境可把 `CRAWLER_TIMEOUT_MS` 调大。
