# 结构化 Agent 提示词设计

## 背景

这个仓库现在已经有 9 个 agent prompt 文件，位置在 `agents/` 目录下。每个文件都已经有长期有效的 `System Prompt` 和每次运行用的 `Weekly User Prompt Template`，这符合项目规则。

目前的问题不是“没有提示词”，而是每个 agent 内部结构不完全一致：有的重点写数据节点状态，有的重点写安全边界，有的重点写输出格式，有的把 workflow、过滤规则和 hard limits 混在一大段文字里。

这次目标是：先统一提示词结构，但不要一次性重写整个 agency。

## 决策

采用两步走：

1. 新增一份共享的结构化提示词标准文档。
2. 先把这个标准应用到两个代表性 agent，作为示范：
   - `agents/08-intent-router.md`
   - `agents/02-ai-information-sentiment-analyst.md`

这个标准不包含 `Initialization` / 初始化章节。

## 提示词标准

每个 agent prompt 建议使用下面这套结构。标题可以保留英文关键词，并在说明里用中文解释，这样后续自动检查也更稳定。

```markdown
# {Agent Name}

## Role

## Profile

## Mission

## Input Sources

## Skills / Data Nodes

## Filtering Rules

## Workflow

## Output Schema

## Hard Limits

## Per-Run User Prompt Template
```

### 每个章节的含义

| 章节 | 作用 |
|---|---|
| `Role` | 用一句话定义 agent 的身份，以及它在系统里的位置。 |
| `Profile` | 定义语言、风格、领域姿态，以及这个 agent 应该像什么样的角色。 |
| `Mission` | 定义这个 agent 负责完成的具体任务，以及它要回答的问题。 |
| `Input Sources` | 定义允许读取的上游材料、原始数据、用户输入，以及禁止替代的来源。 |
| `Skills / Data Nodes` | 定义可用 skills / tools；它们只能作为数据输入节点或 reasoning lens，并且要记录状态。 |
| `Filtering Rules` | 定义纳入、排除、排序、去重、证据等级和控噪规则。 |
| `Workflow` | 定义这个 agent 的执行步骤和推理顺序。 |
| `Output Schema` | 定义这个 agent 必须输出的固定 markdown 格式。 |
| `Hard Limits` | 定义安全边界、禁止行为、证据边界和不得编造的规则。 |
| `Per-Run User Prompt Template` | 定义每次运行时需要填入的变量和任务说明。 |

## 范围

### 本次包含

- 新增一份可长期复用的提示词标准文档。
- 先改造两个 agent 文件作为示范。
- 保留现有投资安全边界：
  - 不自动交易；
  - 不读取或操作真实账户；
  - 不给仓位建议；
  - 不输出下单指令；
  - 只允许研究型 rating。
- 保留现有证据纪律：
  - skills / plugins 是数据输入节点，不是最终推理权威；
  - 区分事实、推断和假设；
  - 数据节点失败或返回不足时必须明确标记；
  - published report 必须先输出 Boss Decision Page；
  - 保留 two-hop evidence linking。

### 本次不包含

- 不一次性批量重写全部 9 个 agent。
- 不改变核心 directed pipeline。
- 不改变周报必需数量要求。
- 不新增或安装 skills / plugins。
- 不接 broker，也不接 paper-trading API。

## 示范 Agent

### Intent Router

`agents/08-intent-router.md` 应该作为“路由型 agent”的标准示范。

它的重点是：

- 识别 task type；
- 判断 selected agents 和 skipped agents；
- 制定 skill / data-node plan；
- 列出缺失输入和默认假设；
- 检查投资安全边界；
- 给出质量门要求；
- 不做投资判断。

它的 `Workflow` 应该明确写成：

1. 阅读用户请求。
2. 判断 task type。
3. 选择 agent 路径。
4. 选择 skill / data-node plan。
5. 找出缺失输入和默认假设。
6. 检查投资安全边界。
7. 输出 Intent Route Plan。

### AI Information & Sentiment Analyst

`agents/02-ai-information-sentiment-analyst.md` 应该作为“研究输入型 agent”的标准示范。

它的重点是：

- 先记录 data-node status；
- 对证据按来源类型去重和分类；
- 区分 fact、opinion、sentiment、developer signal、paper signal 和 market narrative；
- 输出必需数量：
  - 10 条 AI 技术新闻；
  - 5 篇 AI 学术论文；
  - 5 个 AI 开源项目；
  - 5 条高信号舆情证据；
- 生成“当前观察版趋势故事”和“长期远演版趋势故事”，并标注 fact / inference / hypothesis；
- 把问题交给 Fundamental、Technical、Reflection 和 Final Trend agents。

它的 `Workflow` 应该明确写成：

1. 记录数据节点状态。
2. 收集并标准化证据。
3. 去重，并筛选 AI / public-market 相关内容。
4. 按来源类型和信号类型分类证据。
5. 聚类叙事主题。
6. 构造当前观察版趋势故事。
7. 构造长期远演版趋势故事，并标注 fact / inference / hypothesis。
8. 输出交给下游 agent 的问题。

## 备选方案

### 只写标准文档

这是最稳的方案，不碰现有 prompt。但缺点是标准仍然偏抽象，后续迁移时还需要重新解释。

### 一次性批量重写

这个方案最快完成迁移，但当前仓库已经有不少未提交改动。一次性重写所有 agent 会让 review 变得很吵，也更容易无意中改变 agent 行为。

### 标准文档 + 两个示范

这是推荐方案。它既能留下清晰标准，又能给出真实可参考的改造样例，同时保持改动范围足够小。示范通过后，剩下的 agent 可以机械迁移。

## 迁移说明

两个示范文件改造时，必须保留现有重要内容，尤其是：

- Intent Router 支持的 task types；
- 必须输出的表格；
- 安全边界；
- 必需来源数量；
- data-node failure handling；
- 当前观察版故事和长期远演版故事的双层结构；
- 禁止交易、账户操作、仓位建议和下单指令。

可以把 `Weekly User Prompt Template` 统一改名为 `Per-Run User Prompt Template`。如果想兼容现有仓库语言，也可以保留提示：

```markdown
## Per-Run User Prompt Template

原名：Weekly User Prompt Template。
```

## 验证方式

实施完成后检查：

- 两个被改造的 agent 文件仍然包含：
  - `Role`;
  - `Profile`;
  - `Mission`;
  - `Input Sources`;
  - `Skills / Data Nodes`;
  - `Filtering Rules`;
  - `Workflow`;
  - `Output Schema`;
  - `Hard Limits`;
  - `Per-Run User Prompt Template`.
- 确认没有新增 `Initialization` / 初始化章节。
- 确认 `agents/README.md` 仍然指向同样的 prompt 文件。
- 确认质量门和安全边界没有被削弱。
- 运行 `rg -n "^## .*Initialization|^## .*初始化" agents docs/structured-agent-prompt-standard.md`，确保没有新增初始化结构章节。
- 实施后运行 `git diff -- agents/08-intent-router.md agents/02-ai-information-sentiment-analyst.md docs/structured-agent-prompt-standard.md`，检查改动范围。

## 验收标准

- 存在共享提示词标准文档：`docs/structured-agent-prompt-standard.md`。
- `agents/08-intent-router.md` 按标准改造完成。
- `agents/02-ai-information-sentiment-analyst.md` 按标准改造完成。
- 两个示范 prompt 的行为与改造前等价，或者比改造前更严格。
- 没有引入 live trading、账户访问、仓位建议、订单执行或 broker 指令。
- 没有删除周报必需数量要求，也没有删除 evidence-linking 要求。
- 新标准和示范 prompt 中都没有 `Initialization` / 初始化章节。
