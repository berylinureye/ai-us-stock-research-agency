# Weekly Brief Backend

本地 API 适配层，给 `frontend/` 调用。

当前重构目标：从单文件后端迁移到 FastAPI 模块化单体，同时保持启动命令和 HTTP API 兼容。详细方案见 [../docs/backend-fastapi-refactor-plan.md](../docs/backend-fastapi-refactor-plan.md)。

## 运行

```bash
python3 backend/server.py --port 8787
```

`backend/server.py` 会继续作为兼容启动入口。目标形态是它只负责解析 `--host` / `--port`、加载 `.env`、启动 `uvicorn`，具体路由和业务逻辑迁移到 `backend/app/`。

前端默认会请求：

```text
http://127.0.0.1:8787/api/weekly-brief
```

健康检查：

```bash
curl http://127.0.0.1:8787/api/health
```

## 模式

默认模式是 `openai`：读取 `.env` 中的 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL`，调用 OpenAI-compatible `/chat/completions`。

如果你已经有独立周报后端，可以用 proxy 模式：

```bash
WEEKLY_BRIEF_UPSTREAM_URL=http://127.0.0.1:9000/api/weekly-brief python3 backend/server.py
```

如果要只测前后端联通：

```bash
WEEKLY_BRIEF_MOCK=1 python3 backend/server.py --port 8787
```

## 目标 API 分组

| Router | Endpoint | 用途 |
|---|---|---|
| `health` | `GET /api/health` | 健康检查、运行模式、模型网关配置状态 |
| `weekly_brief` | `POST /api/weekly-brief` | 生成周报，支持 JSON 和 `text/event-stream` |
| `pond` | `GET /api/pond` | 读取关注池塘 |
| `pond` | `POST /api/pond/select` | 选择候选进入观察池 |
| `pond` | `POST /api/pond/refresh` | 刷新收盘价和归因字段 |
| `reports` | `GET /api/reports` | 读取报告历史列表 |
| `reports` | `GET /api/reports/{id}` | 读取单份历史报告 |

## 目标分层

```text
backend/app/
├── main.py                # FastAPI app / Front Controller
├── routers/               # HTTP endpoint 分组
├── services/              # WeeklyBriefService、workflow、报告组装、模型网关预检
├── clients/               # OpenAI-compatible、Finnhub、Yahoo、GitHub、arXiv、SEC、FRED
├── repositories/          # 报告历史、池塘 CSV/JSON 读写
├── schemas/               # Pydantic DTO
└── core/                  # config、env、errors、time / markdown utils
```

设计口径：

- FastAPI app + routers 是 Front Controller。
- `WeeklyBriefService` 是 Facade，路由不直接关心 agent workflow 和数据节点细节。
- 外部数据源走 Strategy / Adapter。
- 报告历史和池塘文件读写走 Repository。
- SSE 流式输出走 Observer / event emitter。

## 返回格式

后端返回：

```json
{
  "title": "报告标题",
  "summaryMarkdown": "# 老板决策页...",
  "reportMarkdown": "# 老板决策页...",
  "evidenceMarkdown": "# 证据包...",
  "researchActionPool": [],
  "agentTrace": [
    {
      "agent": "Intent Router",
      "status": "success",
      "headline": "已判断本次任务路径。",
      "thinking": "我先判断用户要跑完整周报还是单点分析。",
      "toolPlan": ["AGENCY.md", "Skill Registry"],
      "findings": ["需要先跑 Stock Discovery"],
      "judgment": "进入完整 directed pipeline。",
      "nextStep": "交给 Stock Discovery。"
    }
  ],
  "runMetadata": {
    "historyId": "..."
  }
}
```

注意：这个适配层不会执行真实交易，也不会读取券商账户。缺实时数据时会要求模型显式标记 `partial` 或 `failed`。

## 重构验收

目标重构完成后至少通过：

```bash
python3 -m unittest discover tests
node tests/frontend-backend-integration.test.mjs
node tests/frontend-start-experience.test.mjs
node tests/error-message-routing.test.mjs
```

新增结构验收：扫描 `backend/**/*.py`，排除 `__pycache__`，断言每个后端 Python 文件 `<2000` 行。
