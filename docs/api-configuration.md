# API 与模型配置清单

更新日期：2026-06-26

本项目只用于 AI 美股投资研究，不用于自动交易、账户操作、下单、调仓或仓位建议。

## 1. LLM 网关配置

当前 `.env` 已配置 Viviai / New API 网关。

| 项 | 当前配置 |
|---|---|
| 网关 | Viviai / New API |
| 接口形态 | OpenAI-compatible |
| Base URL | `https://api.viviai.cc/v1` |
| 默认模型 | `gpt-5.5` |
| 快速模型 | `gpt-5.4-mini` |
| Key 变量 | `OPENAI_API_KEY` |

说明：

- 本地原来已有 `ANTHROPIC_API_KEY` 和 `ANTHROPIC_BASE_URL=https://api.viviai.cc`。
- 实测该网关的 `/v1/models` 和 `/v1/chat/completions` 是 OpenAI-compatible。
- 为了兼容更多脚本，`.env` 已把同一把 key 复制到 `OPENAI_API_KEY`，并设置 `OPENAI_BASE_URL=https://api.viviai.cc/v1`。
- 默认选择 `gpt-5.5`，原因是每周研究简报需要更强的长文综合、结构化输出、推理和中文表达。
- `gpt-5.4-mini` 适合低成本快速子任务，例如格式整理、短摘要和批量清洗。

已从网关模型列表确认可用模型包括：

- `gpt-5.5`
- `gpt-5.4`
- `gpt-5.4-mini`
- `gpt-5.2`
- `gemini-3-pro-preview`
- `gemini-3-flash-preview`
- `gemini-2.5-pro`
- `gemini-2.5-flash`

## 2. 必须或强烈建议人工开通的 API

| 用途 | 变量名 | 优先级 | 开通链接 | 备注 |
|---|---|---:|---|---|
| YouTube 字幕、频道、视频检索 | `TRANSCRIPT_API_KEY` | 高 | https://transcriptapi.com/ | `youtube-full` 必需；用于播客和 YouTube 信息摄取。TranscriptAPI 页面提示安装 ClawHub `transcriptapi` skill 时，本项目等价做法是配置该 key 给已安装的 `youtube-full`，不要重复安装同功能 skill |
| 社交平台抓取增强 | `SCRAPECREATORS_API_KEY` | 高 | https://scrapecreators.com/ | `last30days` 主推荐 key；可增强 X、YouTube、TikTok、Instagram、Reddit 等公开数据抓取 |
| Alpha Vantage 财务/行情补充 | `ALPHA_VANTAGE_API_KEY` | 中 | https://www.alphavantage.co/support/#api-key | 免费额度较小；作为基本面和技术面辅助源 |
| Finnhub 财务/新闻/quote 补充 | `FINNHUB_API_KEY` | 中 | https://finnhub.io/register | 免费端点有限；适合 quote、profile、peers、earnings、metrics、news |
| FRED 宏观数据 | `FRED_API_KEY` | 中 | https://fred.stlouisfed.org/docs/api/api_key.html | 利率、CPI、就业、VIX、treasury 等宏观背景 |
| SEC EDGAR User-Agent | `SEC_EDGAR_USER_AGENT` | 高 | https://www.sec.gov/os/accessing-edgar-data | 不需要 key，但要填真实姓名/邮箱，避免 SEC 请求被拒 |
| BibiGPT 视频/音频总结 | `BIBI_API_TOKEN` | 中 | https://bibigpt.co/user/integration | 有桌面登录时可不填；API 模式需要 token |

## 3. 可选增强 API

| 用途 | 变量名 | 开通链接 | 什么时候需要 |
|---|---|---|---|
| Deep Research / grounded web answer | `PERPLEXITY_API_KEY` | https://docs.perplexity.ai/ | `last30days --deep-research` 或需要更强搜索型总结时 |
| 多模型路由备用 | `OPENROUTER_API_KEY` | https://openrouter.ai/docs/quickstart | 作为 Perplexity 或其他模型网关备份 |
| Web search backend | `BRAVE_API_KEY` | https://brave.com/search/api/ | last30days 需要 headless web search 时 |
| Web search backend | `EXA_API_KEY` | https://exa.ai/ | 语义搜索/研究型检索增强 |
| Google SERP backend | `SERPER_API_KEY` | https://serper.dev/ | Google 搜索结果 API |
| Parallel search backend | `PARALLEL_API_KEY` | https://parallel.ai/ | last30days 的可选 web backend |

这些 key 不是第一版周报必须项。没有它们时，相关数据节点应标记为 `partial`，不能编造补齐。

## 4. 不需要 key 或暂不需要人工配置的源

| Skill / 源 | 配置状态 | 注意事项 |
|---|---|---|
| `financial-data-collector` | 无 key | 使用 yfinance 等免费源，可能有延迟或字段缺失 |
| `yahoo-finance` | 无 key | 非官方接口，可能变化 |
| `nasdaq-data` | 无 key | Nasdaq 内部接口，可能变化 |
| `finviz` | 无 key | HTML scraping，需尊重频率 |
| `tradingview` | 无 key | 公共内部接口，可能变化 |
| `global-stock-data` | 无 key；需要 Python `requests` | 已安装；作为美股/港股行情、K-line、技术指标、基本面和 SEC filing 备份验证源 |
| `cboe-data` | 无 key | 公共数据接口，可能变化 |
| `ak-rss-digest` | 无 key | RSS/文章类输入 |
| `transcript-polisher` | 无 key | 文本清洗，不是数据源 |
| `technical-analyst` | 无 key | 技术分析框架，需要上游提供图表或价格数据 |

## 4.1 YouTube / TranscriptAPI Skill 选择

本项目已经安装 `youtube-full`，它本身就是 TranscriptAPI-backed YouTube skill。

覆盖能力：

- 单个 YouTube 视频 transcript。
- YouTube video / channel search。
- channel latest。
- channel videos。
- channel search。
- playlist videos。

因此，当 TranscriptAPI onboarding 页面提示：

```text
Install transcriptapi skill from clawhub and configure it. My API key is: ...
```

在本项目中不要重复安装同功能 skill。正确做法是：

```bash
TRANSCRIPT_API_KEY=...
```

然后让 AI Information & Sentiment Analyst 调用 `youtube-full`。

只有在未来明确决定用 ClawHub `transcriptapi` 替换 `youtube-full` 时，才考虑安装它。

## 5. Longbridge

当前本机未检测到 `longbridge` CLI。

如果后续要启用 Longbridge 行情、K 线、财报、研究和 market intelligence：

```bash
brew tap longbridge/tap
brew install longbridge/tap/longbridge-terminal
longbridge auth login
```

只启用 read-only / data / research 权限。不要启用交易、下单、账户资金、调仓或组合操作权限。

官方入口：

- https://open.longbridge.com

## 6. 本地填写建议

`.env` 不会提交到 Git。填 key 时只改 `.env`，不要改 `.env.example`。

最低可运行组合：

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.viviai.cc/v1
OPENAI_MODEL=gpt-5.5
TRANSCRIPT_API_KEY=...
SCRAPECREATORS_API_KEY=...
SEC_EDGAR_USER_AGENT="Your Name your.email@example.com"
```

完整研究增强组合：

```bash
ALPHA_VANTAGE_API_KEY=...
FINNHUB_API_KEY=...
FRED_API_KEY=...
BIBI_API_TOKEN=...
PERPLEXITY_API_KEY=...
OPENROUTER_API_KEY=...
BRAVE_API_KEY=...
EXA_API_KEY=...
SERPER_API_KEY=...
```

缺任何一个数据源时，周报必须把对应节点标记为 `partial` 或 `failed`，不得补编内容。
