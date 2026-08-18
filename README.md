# AI Tracing

公司内部 AI 技术每日动态系统。

## 仓库结构

- `apps/api`：系统后端，FastAPI
- `apps/web`：前端，Vue 3 + Vite
- `docs`：产品和接口文档
- `scripts`：本地开发脚本
- `deploy`：服务器部署说明

## 本地开发（Windows）

```powershell
.\scripts\run-api.ps1
.\scripts\run-web.ps1
```

## 服务器部署（Linux）

见 [deploy/server-linux.md](deploy/server-linux.md)

## 说明

- `run-api.ps1` 和 `run-web.ps1` 只用于本机 Windows 开发。
- 服务器部署不要照着这两个 PowerShell 脚本走，应使用 Linux 说明。
- 爬虫后端在独立仓库 `AI-Tracing-Crawler` 中运行，系统后端通过 HTTP 调用它。
