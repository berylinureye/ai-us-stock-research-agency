# AI 美股周报研究台 Frontend

这是一个零依赖静态前端，用来接入现有周报生成 API。

## 运行

```bash
python3 -m http.server 5173 --directory frontend
```

然后打开：

```text
http://localhost:5173
```

## 默认 API

前端默认 `POST http://127.0.0.1:8787/api/weekly-brief`。页面右上角 `API` 可以改 endpoint，并保存在浏览器 `localStorage`。

本仓库已经提供一个本地后端适配层：

```bash
python3 backend/server.py --port 8787
```

请求体会包含：

```json
{
  "prompt": "用户输入",
  "workflow": "weekly_ai_us_equity_research",
  "market": "US",
  "language": "zh-CN",
  "model": "gpt-5.5",
  "output": {
    "format": "markdown",
    "include_summary": true,
    "include_evidence_pack": true,
    "two_hop_evidence_links": true
  }
}
```

## 支持的响应

最推荐：

```json
{
  "title": "本周 AI 美股研究周报",
  "summaryMarkdown": "# 老板决策页...",
  "reportMarkdown": "# 老板决策页...",
  "evidenceMarkdown": "# 证据包...",
  "agentTrace": [
    {
      "agent": "Reflection",
      "status": "partial",
      "headline": "木头姐看长期创新扩散，巴菲特质疑现金流和估值。",
      "thinking": "我正在比较长期 AI 叙事和价值纪律是否能同时成立。",
      "toolPlan": ["Cathie Wood lens", "Buffett lens", "上游 section 证据"],
      "findings": ["长期 TAM 可能被低估", "当前现金流证据仍不足"],
      "judgment": "故事可以保留，但必须降级为待验证。",
      "nextStep": "交给 Final Narrative，只保留证据链支撑的部分。"
    }
  ]
}
```

也支持这些形态：

- 纯 `text/markdown` 或 `text/plain`。
- `{ "markdown": "..." }`。
- `{ "files": [{ "name": "weekly.md", "content": "..." }, { "name": "weekly.evidence.md", "content": "..." }] }`。
- `text/event-stream` / `application/x-ndjson`，字段可包含 `stage`、`status`、`delta`、`markdown`、`reportMarkdown`、`evidenceMarkdown`、`thinkingTrace`。

前端会把 `thinkingTrace` 渲染成“Agent 思考轨迹”：我在判断什么、调用/需要哪些数据节点、看到什么信号、当前判断和下一步。原始 section Markdown 只放在折叠区，避免工作流侧栏变成参数表和未整理 Markdown。

前端会把精简版、完整周报和双跳证据都渲染成可点击 Markdown，并提供 `.md` 下载。
