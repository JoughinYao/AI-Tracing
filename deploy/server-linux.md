# Linux 服务器部署说明（无 sudo 版本）

本文档用于把系统部署到公司内网 Linux 服务器。当前方案不依赖 Nginx、systemd 或 sudo 权限，适合普通用户账号部署和测试。

## 端口

- 系统后端：`8100`
- 爬虫后端：`8101`
- 前端：`5174`

如果端口被占用，先用下面命令检查：

```bash
ss -ltnp | grep -E ':(8100|8101|5174)\b'
```

无输出通常表示端口未被占用。

## 代码目录

建议目录：

```bash
mkdir -p ~/apps
cd ~/apps
git clone https://github.com/JoughinYao/AI-Tracing.git
git clone https://github.com/JoughinYao/AI-Tracing-Crawler.git
```

如果服务器无法访问 GitHub，可以在本地打包后上传。

## 系统后端配置

```bash
cd ~/apps/AI-Tracing/apps/api
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
```

编辑 `~/apps/AI-Tracing/apps/api/.env`：

```env
DATABASE_URL=sqlite:///./ai_tracing.db
CRAWLER_BASE_URL=http://127.0.0.1:8101
CRAWLER_TIMEOUT_MS=1200000
FRONTEND_ORIGIN=http://10.159.3.80:5174
ANTHROPIC_API_URL=https://new-api.finstep.cn
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6
RANKING_LLM_ENABLED=true
RANKING_LLM_TIMEOUT_MS=60000
RANKING_LLM_MAX_RETRIES=2
ENABLE_SCHEDULER=true
SCHEDULER_TIMEZONE=Asia/Shanghai
```

启动：

```bash
cd ~/apps/AI-Tracing
bash scripts/run-api.sh
```

## 爬虫后端配置

```bash
cd ~/apps/AI-Tracing-Crawler
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env
```

编辑 `~/apps/AI-Tracing-Crawler/.env`，重点确认：

```env
OPENAI_BASE_URL=https://new-api.finstep.cn/v1
OPENAI_API_KEY=
OPENAI_MODEL=claude-sonnet-4-6
GITHUB_TOKEN=
CRAWLER_PORT=8101
CRAWLER_TIMEOUT_MS=1200000
SYSTEM_BACKEND_URL=http://127.0.0.1:8100
```

启动：

```bash
cd ~/apps/AI-Tracing-Crawler
./venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8101 --log-level info
```

## 前端配置

确认 `~/apps/AI-Tracing/apps/web/vite.config.ts` 允许内网 IP 访问：

```ts
server: {
  host: "0.0.0.0",
  port: 5174,
  allowedHosts: ["10.159.3.80"],
  proxy: {
    "/api": {
      target: "http://127.0.0.1:8100",
      changeOrigin: true,
    },
  },
},
```

启动：

```bash
cd ~/apps/AI-Tracing
bash scripts/run-web.sh
```

浏览器访问：

```text
http://10.159.3.80:5174
```

## 三个服务分别验证

```bash
curl http://127.0.0.1:8100/api/home/today
curl http://127.0.0.1:8101/health
curl http://10.159.3.80:5174
```

## 不中断运行

没有 sudo 权限时不能配置 systemd。可以临时使用 `tmux`：

```bash
tmux new -s ai-api
bash scripts/run-api.sh
```

按 `Ctrl+B`，再按 `D` 退出会话但保留进程。

爬虫和前端分别开新的 tmux 会话：

```bash
tmux new -s ai-crawler
tmux new -s ai-web
```

重新进入会话：

```bash
tmux attach -t ai-api
tmux attach -t ai-crawler
tmux attach -t ai-web
```

如果服务器没有 `tmux`，且你没有 sudo，使用普通终端启动时关闭 SSH 会导致服务停止。
