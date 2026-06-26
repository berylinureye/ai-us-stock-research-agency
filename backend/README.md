# Weekly Brief Backend

本地 API 适配层，给 `frontend/` 调用。

## 运行

```bash
python3 backend/server.py --port 8787
```

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

## 返回格式

后端返回：

```json
{
  "title": "报告标题",
  "summaryMarkdown": "# 老板决策页...",
  "reportMarkdown": "# 老板决策页...",
  "evidenceMarkdown": "# 证据包...",
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
  ]
}
```

注意：这个适配层不会执行真实交易，也不会读取券商账户。缺实时数据时会要求模型显式标记 `partial` 或 `failed`。
