# Agent Visible Trace

返回：[AGENCY](../AGENCY.md) · [Frontend README](../frontend/README.md) · [Backend README](../backend/README.md)

Agent Visible Trace 是给用户看的公开工作轨迹，不是隐藏 chain-of-thought。它要让用户看到 agent 正在推进什么、调用/需要什么数据、看到了什么证据或缺口、当前判断是什么、下一步交给谁。

## 设计目标

- 像研究员在现场解释工作，而不是把未整理 Markdown、参数表或状态表直接塞给用户。
- 只展示公开、可审计的 reasoning summary。
- 不输出隐藏推理链、内部草稿、未经证实的事实或工具密钥。
- 原始 section Markdown 可以保留，但必须折叠在“查看原始 section 输出”里。

## Schema

```json
{
  "agent": "Reflection",
  "stepIndex": 6,
  "stepTotal": 8,
  "status": "partial",
  "headline": "木头姐看长期创新扩散，巴菲特质疑现金流和估值。",
  "thinking": "我正在比较长期 AI 叙事和价值纪律是否能同时成立。",
  "toolPlan": ["Cathie Wood lens", "Buffett lens", "上游 section 证据"],
  "findings": ["长期 TAM 可能被低估", "当前现金流证据仍不足"],
  "judgment": "故事可以保留，但必须降级为待验证。",
  "nextStep": "交给 Final Narrative，只保留证据链支撑的部分。",
  "debate": {
    "cathieWood": "长期创新扩散可能被低估。",
    "buffett": "现金流、护城河和安全边际仍不足。",
    "synthesis": "保留长期情景，但降低短期 conviction。"
  }
}
```

## UI 呈现

每个 agent 卡片默认展示：

- 我现在在判断
- 调用 / 需要的数据节点
- 我看到的信号
- 当前判断
- 下一步
- Reflection 阶段额外展示 Wood vs Buffett 反方审查

禁止默认展示：

- 未折叠的大段 Markdown
- 大参数表
- 原始 JSON
- 隐藏推理链
- 未核验的新闻、行情、财务数字或链接
