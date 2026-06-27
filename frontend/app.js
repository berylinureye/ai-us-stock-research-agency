(function () {
  "use strict";

  const STORAGE = {
    endpoint: "weeklyBrief.endpoint",
    token: "weeklyBrief.token"
  };

  const DEFAULT_ENDPOINT = "http://127.0.0.1:8787/api/weekly-brief";
  const DEFAULT_RESEARCH_INTENT = "请先按美股全市场周报流程做一次机会扫描，默认发现最多 8 个候选，输出中文研究周报和双跳证据。";
  const DEFAULT_RESEARCH_LABEL = "直接开始：美股全市场机会扫描";
  const LEGACY_ENDPOINTS = new Set([
    "http://localhost:8000/api/weekly-brief",
    "http://127.0.0.1:8000/api/weekly-brief"
  ]);

  const WORKFLOW_STEPS = [
    ["Intent Router", "判断任务路径、输入边界和缺失配置"],
    ["Stock Discovery", "候选池发现，默认最多 8 个 active candidates"],
    ["AI 信息与舆情", "新闻、论文、开源项目和高信号舆情"],
    ["Fundamental", "财报、SEC、估值和财务传导链"],
    ["Technical", "价格行为、支撑阻力和市场状态"],
    ["Reflection", "Cathie Wood vs Buffett 反方审查"],
    ["Final Narrative", "老板决策页、Top 5 和双跳证据"],
    ["Paper Attribution", "shadow ledger 观察与归因"]
  ];

  const THINKING_WORDS = ["研判中", "检索证据", "校验链路", "形成周报"];
  const ESTIMATED_RUN_MS = 12 * 60 * 1000;
  const TRACE_AGENT_DEFAULTS = {
    "Intent Router": {
      thinking: "我先判断这次请求属于哪些任务、哪些 agent 应该运行，以及哪些数据节点缺失。",
      nextStep: "按路由结果进入下一层，报告首页仍从老板决策页开始。"
    },
    "Stock Discovery": {
      thinking: "我先从候选入口控噪，找出哪些公司值得继续验证。",
      nextStep: "交给信息、基本面和技术面做交叉验证。"
    },
    "AI 信息与舆情": {
      thinking: "我先检查近期信息流里哪些叙事反复出现，哪些证据足够高信号。",
      nextStep: "把能成立的故事交给基本面验证财务传导。"
    },
    Fundamental: {
      thinking: "我先验证故事能不能传导到收入、利润、现金流、capex、margin 或估值预期。",
      nextStep: "把财务上能站住的候选交给技术面确认时机和风险位。"
    },
    Technical: {
      thinking: "我先看价格、K 线、量能和关键位，确认叙事有没有被市场行为支持。",
      nextStep: "把图表支持、犹豫或反对的信号交给 Reflection。"
    },
    Reflection: {
      thinking: "我先用长期创新视角和价值纪律分别审查这个故事是否站得住。",
      nextStep: "把双方分歧交给 Final Narrative，只保留证据链能支撑的部分。"
    },
    "Final Narrative": {
      thinking: "我先把前面几层证据收束成老板能先看的结论、Top 5、风险和下周验证。",
      nextStep: "把可观察候选交给池塘和 shadow ledger，等待复盘。"
    },
    "Paper Attribution": {
      thinking: "我先把观察对象和价格结果对齐，判断 thesis、时机或市场环境分别造成了什么影响。",
      nextStep: "更新信号权重和下周观察规则。"
    }
  };
  const TRACE_NODE_PATTERNS = [
    ["YouTube / 播客", /youtube|podcast|transcript|播客|访谈|发言|字幕/i],
    ["last30days / 社区舆情", /last30days|reddit|twitter|社区|舆情|讨论/i],
    ["GitHub / 开源项目", /github|repo|开源|star|fork/i],
    ["arXiv / 论文", /arxiv|paper|论文/i],
    ["RSS / 新闻", /rss|news|新闻|媒体/i],
    ["SEC / filings", /sec|10-k|10-q|8-k|filing|edgar|年报|季报/i],
    ["基本面数据", /财报|收入|利润|现金流|估值|margin|capex|eps|fundamental/i],
    ["行情 / K 线", /k-line|k线|ohlcv|价格|支撑|阻力|均线|rsi|macd|技术/i],
    ["Wood / Buffett 视角", /cathie|wood|木头姐|buffett|巴菲特|reflection|反方/i]
  ];

  const els = {
    canvas: document.getElementById("marketCanvas"),
    form: document.getElementById("researchForm"),
    prompt: document.getElementById("promptInput"),
    endpoint: document.getElementById("endpointInput"),
    token: document.getElementById("tokenInput"),
    apiStatus: document.getElementById("apiStatus"),
    testConnection: document.getElementById("testConnectionButton"),
    settingsToggle: document.getElementById("settingsToggle"),
    settingsPanel: document.getElementById("settingsPanel"),
    reportHistoryNavButton: document.getElementById("reportHistoryNavButton"),
    pondNavButton: document.getElementById("pondNavButton"),
    pondPreviewMeta: document.getElementById("pondPreviewMeta"),
    pondPreviewTickers: document.getElementById("pondPreviewTickers"),
    pondPreviewButton: document.getElementById("pondPreviewButton"),
    topbar: document.getElementById("topbar"),
    backButton: document.getElementById("backButton"),
    hero: document.getElementById("heroSection"),
    workspace: document.getElementById("workspaceSection"),
    result: document.getElementById("resultSection"),
    reportHistory: document.getElementById("reportHistorySection"),
    pond: document.getElementById("pondSection"),
    messageList: document.getElementById("messageList"),
    workflowOutput: document.getElementById("workflowOutput"),
    workflowOutputList: document.getElementById("workflowOutputList"),
    workflowOutputCount: document.getElementById("workflowOutputCount"),
    workflowList: document.getElementById("workflowList"),
    streamLog: document.getElementById("streamLog"),
    thinkingWord: document.getElementById("thinkingWord"),
    thinkingPanel: document.getElementById("thinkingPanel"),
    progressElapsed: document.getElementById("progressElapsed"),
    progressPercent: document.getElementById("progressPercent"),
    progressEstimate: document.getElementById("progressEstimate"),
    progressTrack: document.getElementById("progressTrack"),
    progressFill: document.getElementById("progressFill"),
    cancelButton: document.getElementById("cancelButton"),
    resultTitle: document.getElementById("resultTitle"),
    candidateSection: document.getElementById("candidateSection"),
    candidateStatus: document.getElementById("candidateStatus"),
    candidateGrid: document.getElementById("candidateGrid"),
    resultMeta: document.getElementById("resultMeta"),
    panelSummary: document.getElementById("panel-summary"),
    panelReport: document.getElementById("panel-report"),
    panelEvidence: document.getElementById("panel-evidence"),
    rawMarkdown: document.getElementById("rawMarkdown"),
    downloadSummary: document.getElementById("downloadSummaryButton"),
    downloadEvidence: document.getElementById("downloadEvidenceButton"),
    downloadFull: document.getElementById("downloadFullButton"),
    pondLastRefresh: document.getElementById("pondLastRefresh"),
    pondReloadButton: document.getElementById("pondReloadButton"),
    pondRefreshButton: document.getElementById("pondRefreshButton"),
    pondOpenCount: document.getElementById("pondOpenCount"),
    pondOpenTable: document.getElementById("pondOpenTable"),
    pondDetailTitle: document.getElementById("pondDetailTitle"),
    pondDetailBody: document.getElementById("pondDetailBody"),
    pondHistoryCount: document.getElementById("pondHistoryCount"),
    pondHistoryList: document.getElementById("pondHistoryList"),
    reportHistoryReloadButton: document.getElementById("reportHistoryReloadButton"),
    reportHistoryCount: document.getElementById("reportHistoryCount"),
    reportHistoryList: document.getElementById("reportHistoryList"),
    reportHistoryDetailTitle: document.getElementById("reportHistoryDetailTitle"),
    reportHistoryDetailMeta: document.getElementById("reportHistoryDetailMeta"),
    reportHistoryDetailBody: document.getElementById("reportHistoryDetailBody")
  };

  const state = {
    controller: null,
    activeStep: 0,
    thinkingTimer: null,
    progressTimer: null,
    runStartedAt: null,
    result: null,
    partialMarkdown: "",
    streamObject: {},
    streamLines: [],
    workflowOutputs: [],
    returningToStart: false,
    view: "home",
    pondData: null,
    reportHistoryData: null,
    selectedReportId: "",
    selectedPondId: "",
    selectedCandidateKeys: new Set()
  };

  init();

  function init() {
    els.endpoint.value = getInitialEndpoint();
    els.token.value = localStorage.getItem(STORAGE.token) || "";
    renderWorkflow(0);
    bindEvents();
    startCanvas();
    checkBackendStatus({ quiet: true });
    loadPondData({ quiet: true });
    syncViewFromHash();
  }

  function bindEvents() {
    els.form.addEventListener("submit", handleSubmit);
    els.settingsPanel.addEventListener("submit", (event) => event.preventDefault());
    els.settingsToggle.addEventListener("click", toggleSettings);
    els.cancelButton.addEventListener("click", () => state.controller && state.controller.abort());
    els.backButton.addEventListener("click", handleBack);
    els.testConnection.addEventListener("click", () => checkBackendStatus({ quiet: false }));
    els.reportHistoryNavButton.addEventListener("click", () => {
      if (!state.controller) window.location.hash = "#/history";
    });
    els.pondNavButton.addEventListener("click", () => {
      if (!state.controller) window.location.hash = "#/pond";
    });
    els.pondPreviewButton.addEventListener("click", () => {
      window.location.hash = "#/pond";
    });
    els.pondReloadButton.addEventListener("click", () => loadPondData({ quiet: false }));
    els.pondRefreshButton.addEventListener("click", refreshPondPrices);
    els.reportHistoryReloadButton.addEventListener("click", () => loadReportHistory({ quiet: false }));
    window.addEventListener("hashchange", syncViewFromHash);

    document.querySelectorAll(".tab-button").forEach((button) => {
      button.addEventListener("click", () => switchTab(button.dataset.tab || "summary"));
    });
    els.downloadSummary.addEventListener("click", () => state.result && downloadMarkdown(state.result.summaryMarkdown, "weekly-brief-summary.md"));
    els.downloadEvidence.addEventListener("click", () => state.result && downloadMarkdown(state.result.evidenceMarkdown, "weekly-brief-evidence.md"));
    els.downloadFull.addEventListener("click", () => state.result && downloadMarkdown(state.result.reportMarkdown, "weekly-brief-full.md"));
  }

  function toggleSettings() {
    const willOpen = els.settingsPanel.hidden;
    els.settingsPanel.hidden = !willOpen;
    els.settingsToggle.setAttribute("aria-expanded", String(willOpen));
    if (willOpen) els.endpoint.focus();
  }

  function handleBack() {
    if (state.view === "pond") {
      window.location.hash = "";
      return;
    }
    resetToStart();
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const rawPrompt = els.prompt.value.trim();
    const prompt = rawPrompt || DEFAULT_RESEARCH_INTENT;
    const displayPrompt = rawPrompt || DEFAULT_RESEARCH_LABEL;
    const endpoint = els.endpoint.value.trim() || DEFAULT_ENDPOINT;
    const token = els.token.value.trim();
    localStorage.setItem(STORAGE.endpoint, endpoint);
    localStorage.setItem(STORAGE.token, token);

    state.partialMarkdown = "";
    state.streamObject = {};
    state.streamLines = [];
    state.workflowOutputs = [];
    state.result = null;
    state.runStartedAt = new Date();
    state.controller = new AbortController();
    state.returningToStart = false;
    enterRunningState(displayPrompt);

    const headers = authHeaders({
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream, text/markdown, text/plain"
    });
    if (token) headers.Authorization = `Bearer ${token}`;

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers,
        body: JSON.stringify(buildPayload(prompt)),
        signal: state.controller.signal
      });
      if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`API ${response.status}: ${body || response.statusText}`);
      }
      const contentType = response.headers.get("content-type") || "";
      if (isStreamingResponse(contentType)) {
        await readStreamingResponse(response, contentType);
        completeRun(normalizeApiPayload(state.streamObject, state.partialMarkdown));
      } else {
        completeRun(normalizeApiPayload(await readWholeResponse(response, contentType)));
      }
    } catch (error) {
      if (state.returningToStart && error.name === "AbortError") return;
      if (error.name === "AbortError") showRunError("已停止本次工作流。");
      else showRunError(friendlyApiError(error, endpoint));
    } finally {
      state.controller = null;
      state.returningToStart = false;
      stopThinkingWords();
      stopRunProgress();
      els.thinkingPanel.setAttribute("aria-busy", "false");
    }
  }

  function getInitialEndpoint() {
    const saved = localStorage.getItem(STORAGE.endpoint);
    if (!saved || LEGACY_ENDPOINTS.has(saved)) {
      localStorage.setItem(STORAGE.endpoint, DEFAULT_ENDPOINT);
      return DEFAULT_ENDPOINT;
    }
    return saved;
  }

  function makeHealthUrl(endpoint) {
    try {
      const url = new URL(endpoint, window.location.href);
      url.pathname = url.pathname.replace(/\/api\/weekly-brief\/?$/, "/api/health");
      url.search = "";
      url.hash = "";
      return url.toString();
    } catch (_error) {
      return "http://127.0.0.1:8787/api/health";
    }
  }

  function makePondUrl(path) {
    const endpoint = els.endpoint.value.trim() || DEFAULT_ENDPOINT;
    try {
      const url = new URL(endpoint, window.location.href);
      url.pathname = url.pathname.replace(/\/api\/weekly-brief\/?$/, path);
      url.search = "";
      url.hash = "";
      return url.toString();
    } catch (_error) {
      return `http://127.0.0.1:8787${path}`;
    }
  }

  function makeReportHistoryUrl(path) {
    const endpoint = els.endpoint.value.trim() || DEFAULT_ENDPOINT;
    try {
      const url = new URL(endpoint, window.location.href);
      url.pathname = url.pathname.replace(/\/api\/weekly-brief\/?$/, path);
      url.search = "";
      url.hash = "";
      return url.toString();
    } catch (_error) {
      return `http://127.0.0.1:8787${path}`;
    }
  }

  function authHeaders(extraHeaders) {
    const headers = { ...(extraHeaders || {}) };
    const token = els.token.value.trim();
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
  }

  async function checkBackendStatus({ quiet }) {
    const endpoint = els.endpoint.value.trim() || DEFAULT_ENDPOINT;
    const healthUrl = makeHealthUrl(endpoint);
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 2500);
    if (!quiet) setApiStatus("checking", "正在检测后端...");
    try {
      const response = await fetch(healthUrl, { headers: authHeaders(), signal: controller.signal });
      if (!response.ok) throw new Error(`Health ${response.status}`);
      const payload = await response.json().catch(() => ({}));
      const mode = payload.mode ? ` / ${payload.mode}` : "";
      const model = payload.model ? ` / ${payload.model}` : "";
      setApiStatus("ok", `已连接${mode}${model}`);
    } catch (error) {
      setApiStatus(quiet ? "idle" : "error", quiet ? "后端未检测，点击检测连接" : friendlyApiError(error, healthUrl));
    } finally {
      window.clearTimeout(timer);
    }
  }

  function setApiStatus(status, text) {
    els.apiStatus.dataset.status = status;
    els.apiStatus.textContent = text;
  }

  function friendlyApiError(error, endpoint) {
    const message = error && error.message ? error.message : String(error || "");
    if (error && error.name === "AbortError") return "连接超时：请确认本地后端已经启动。";
    if (/Failed to fetch|NetworkError|Load failed/i.test(message)) {
      return `没有连上后端：请启动 backend/server.py，或在 API 面板检查 endpoint。当前 endpoint：${endpoint}`;
    }
    if (/模型网关额度不足|insufficient_quota|current quota|billing|API 429|429/i.test(message)) {
      return "模型网关额度不足：OpenAI 返回 429 insufficient_quota。请检查 API 账户余额、计费计划，或更换可用的 OPENAI_API_KEY。";
    }
    if (/模型网关鉴权失败|OPENAI_API_KEY|OPENAI_BASE_URL|OPENAI_MODEL|api\.viviai\.cc/i.test(message)) {
      return "模型网关鉴权失败：请检查 .env 里的 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL，或确认当前 key 有这个模型权限。这不是 Local Auth Token 问题。";
    }
    if (/API 401|Health 401|Unauthorized/i.test(message)) {
      return "后端返回 401：需要在 API 面板填写 Local Auth Token，或关闭后端鉴权。";
    }
    if (/API 404|Health 404|Not found/i.test(message)) return `后端地址能访问，但路径不对：${endpoint}`;
    return message || "API 调用失败。";
  }

  function buildPayload(prompt) {
    return {
      prompt,
      user_prompt: prompt,
      intent: prompt,
      workflow: "weekly_ai_us_equity_research",
      market: "US",
      language: "zh-CN",
      model: "gpt-5.5",
      output: {
        format: "markdown",
        include_summary: true,
        include_evidence_pack: true,
        two_hop_evidence_links: true,
        include_research_action_pool: true
      },
      guardrails: {
        research_only: true,
        no_trading_orders: true,
        no_position_sizing: true
      }
    };
  }

  function enterRunningState(prompt) {
    state.view = "running";
    setTopbarMode("running");
    els.cancelButton.hidden = false;
    els.cancelButton.disabled = false;
    els.hero.hidden = true;
    els.result.hidden = true;
    els.reportHistory.hidden = true;
    els.pond.hidden = true;
    els.workspace.hidden = false;
    els.messageList.innerHTML = "";
    clearWorkflowOutputs();
    els.streamLog.textContent = "正在连接 API...";
    addMessage("user", "你", prompt);
    addMessage("assistant", "研究台", "我会先跑 Intent Router，再生成包含老板决策页和 evidence pack 的中文周报。");
    renderWorkflow(0);
    startThinkingWords();
    startRunProgress();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function resetToStart() {
    if (state.controller) {
      state.returningToStart = true;
      state.controller.abort();
    }
    stopThinkingWords();
    stopRunProgress();
    resetRunProgress();
    state.view = "home";
    setTopbarMode("home");
    els.cancelButton.hidden = true;
    els.cancelButton.disabled = true;
    els.hero.hidden = false;
    els.workspace.hidden = true;
    els.result.hidden = true;
    els.reportHistory.hidden = true;
    els.pond.hidden = true;
    els.thinkingPanel.setAttribute("aria-busy", "false");
    els.streamLog.textContent = "";
    clearWorkflowOutputs();
    renderWorkflow(0);
    window.setTimeout(() => els.prompt.focus(), 0);
  }

  function setTopbarMode(mode) {
    const isRunning = mode === "running";
    const isHome = mode === "home" || mode === "start";
    els.topbar.classList.toggle("is-running", isRunning || mode === "detail");
    els.backButton.hidden = isHome;
    els.reportHistoryNavButton.disabled = isRunning;
    els.pondNavButton.disabled = isRunning;
  }

  function syncViewFromHash() {
    if (state.controller) return;
    if (window.location.hash === "#/pond") showPondView();
    else if (window.location.hash === "#/history") showReportHistoryView();
    else if (state.view === "pond") showHomeView();
    else if (state.view === "history") showHomeView();
  }

  function showHomeView() {
    state.view = "home";
    setTopbarMode("home");
    els.hero.hidden = false;
    els.workspace.hidden = true;
    els.result.hidden = true;
    els.reportHistory.hidden = true;
    els.pond.hidden = true;
    loadPondData({ quiet: true });
  }

  function showPondView() {
    state.view = "pond";
    setTopbarMode("detail");
    els.hero.hidden = true;
    els.workspace.hidden = true;
    els.result.hidden = true;
    els.reportHistory.hidden = true;
    els.pond.hidden = false;
    loadPondData({ quiet: false });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function showReportHistoryView() {
    state.view = "history";
    setTopbarMode("detail");
    els.hero.hidden = true;
    els.workspace.hidden = true;
    els.result.hidden = true;
    els.reportHistory.hidden = false;
    els.pond.hidden = true;
    loadReportHistory({ quiet: false });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function startThinkingWords() {
    stopThinkingWords();
    let index = 0;
    els.thinkingWord.textContent = THINKING_WORDS[index];
    state.thinkingTimer = window.setInterval(() => {
      index = (index + 1) % THINKING_WORDS.length;
      els.thinkingWord.textContent = THINKING_WORDS[index];
    }, 2200);
    els.thinkingPanel.setAttribute("aria-busy", "true");
  }

  function stopThinkingWords() {
    if (state.thinkingTimer) window.clearInterval(state.thinkingTimer);
    state.thinkingTimer = null;
  }

  function startRunProgress() {
    stopRunProgress();
    updateRunProgress();
    state.progressTimer = window.setInterval(updateRunProgress, 1000);
  }

  function stopRunProgress() {
    if (state.progressTimer) window.clearInterval(state.progressTimer);
    state.progressTimer = null;
  }

  function resetRunProgress() {
    setRunProgress(0);
    els.progressElapsed.textContent = "00:00";
    els.progressEstimate.textContent = "预计 12:00";
  }

  function completeRunProgress() {
    stopRunProgress();
    const elapsedMs = state.runStartedAt ? Date.now() - state.runStartedAt.getTime() : 0;
    setRunProgress(100);
    els.progressElapsed.textContent = formatDuration(elapsedMs);
    els.progressEstimate.textContent = "完成";
  }

  function updateRunProgress() {
    if (!state.runStartedAt) return resetRunProgress();
    const elapsedMs = Date.now() - state.runStartedAt.getTime();
    const percent = Math.max(Math.min((elapsedMs / ESTIMATED_RUN_MS) * 100, 99), 2);
    const remainingMs = Math.max(ESTIMATED_RUN_MS - elapsedMs, 0);
    setRunProgress(percent);
    els.progressElapsed.textContent = formatDuration(elapsedMs);
    els.progressEstimate.textContent = remainingMs ? `预计剩余 ${formatDuration(remainingMs)}` : "超过 12 分钟，继续收尾";
  }

  function setRunProgress(percent) {
    const safePercent = Math.max(0, Math.min(percent, 100));
    els.progressFill.style.width = `${safePercent}%`;
    els.progressPercent.textContent = `${Math.round(safePercent)}%`;
    els.progressTrack.setAttribute("aria-valuenow", String(Math.round(safePercent)));
    els.progressTrack.setAttribute("aria-valuetext", `${Math.round(safePercent)}%`);
  }

  function formatDuration(milliseconds) {
    const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
    return `${String(Math.floor(totalSeconds / 60)).padStart(2, "0")}:${String(totalSeconds % 60).padStart(2, "0")}`;
  }

  function formatClockTime(date) {
    return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  }

  function addMessage(type, label, text) {
    const item = document.createElement("div");
    item.className = `message ${type}`;
    item.innerHTML = `<span class="label">${escapeHtml(label)}</span><p>${escapeHtml(text)}</p>`;
    els.messageList.appendChild(item);
  }

  function clearWorkflowOutputs() {
    state.workflowOutputs = [];
    els.workflowOutput.hidden = true;
    els.workflowOutputList.innerHTML = "";
    els.workflowOutputCount.textContent = "0 条";
  }

  function addWorkflowOutput(output) {
    const fullText = String(output.fullText || "").trim();
    const trace = normalizeAgentTrace(output.trace, {
      agent: output.agent,
      status: output.stage,
      headline: output.preview,
      fullText
    });
    const preview = publicThinkingPreview(trace);
    if (!preview && !fullText && !trace.headline) return;
    state.workflowOutputs.push({
      agent: trace.agent || output.agent || "Workflow",
      stage: trace.status || output.stage || "输出",
      preview,
      fullText: fullText || preview,
      trace,
      time: formatClockTime(new Date())
    });
    renderWorkflowOutputs();
  }

  function renderWorkflowOutputs() {
    els.workflowOutput.hidden = state.workflowOutputs.length === 0;
    els.workflowOutputCount.textContent = `${state.workflowOutputs.length} 条`;
    els.workflowOutputList.innerHTML = "";
    state.workflowOutputs.forEach((output) => {
      const item = document.createElement("details");
      item.className = "workflow-output-item";
      const summary = document.createElement("summary");
      summary.className = "workflow-output-summary";
      summary.setAttribute("role", "button");
      summary.setAttribute("aria-expanded", "false");
      summary.innerHTML = `
        <span class="workflow-output-meta"><strong>${escapeHtml(output.agent)}</strong><span>${escapeHtml(output.stage)} · ${escapeHtml(output.time)}</span></span>
        <span class="workflow-output-preview">${escapeHtml(output.preview)}</span>
        <span class="workflow-output-toggle" aria-hidden="true">展开</span>
      `;
      const body = renderAgentTrace(output);
      item.append(summary, body);
      const setOpen = (open) => {
        summary.setAttribute("aria-expanded", String(open));
        const toggle = item.querySelector(".workflow-output-toggle");
        if (toggle) toggle.textContent = open ? "收起" : "展开";
      };
      item.addEventListener("toggle", () => {
        setOpen(item.open);
      });
      els.workflowOutputList.appendChild(item);
    });
  }

  function normalizeAgentTrace(trace, fallback) {
    const source = trace && typeof trace === "object" ? trace : {};
    const fullText = String(fallback.fullText || source.fullText || source.sectionMarkdown || source.section_markdown || "").trim();
    const agent = firstString(source, ["agent", "section", "sectionName"]) || fallback.agent || inferAgentFromStage(fallback.status);
    const defaults = TRACE_AGENT_DEFAULTS[agent] || {};
    const findings = source.findings || source.signals || source.observations || [];
    return {
      agent,
      status: firstString(source, ["status", "stage", "step"]) || fallback.status || "输出",
      headline: firstString(source, ["headline", "summary", "preview"]) || fallback.headline || makePreview(fullText),
      thinking: firstString(source, ["thinking", "thinkingSummary", "thinking_summary", "reasoningSummary", "reasoning_summary"]) || defaults.thinking || "",
      judgment: firstString(source, ["judgment", "decision", "rationale", "conclusion"]) || makePreview(fullText),
      nextStep: firstString(source, ["nextStep", "next_step"]) || defaults.nextStep || "",
      toolPlan: toStringList(source.toolPlan || source.tool_plan || source.dataNodes || source.data_nodes).concat(inferTraceNodes(fullText)),
      findings: toStringList(findings).length ? toStringList(findings) : extractTraceFindings(fullText),
      debate: source.debate && typeof source.debate === "object" ? source.debate : inferDebate(agent, fullText)
    };
  }

  function publicThinkingPreview(trace) {
    const thinking = String(trace && trace.thinking ? trace.thinking : "").replace(/\s+/g, " ").trim();
    if (thinking) return thinking;
    return "我正在整理这个 agent 的公开判断。";
  }

  function renderAgentTrace(output) {
    const trace = output.trace || normalizeAgentTrace(null, output);
    const body = document.createElement("div");
    body.className = "agent-trace-body";
    const grid = document.createElement("div");
    grid.className = "agent-trace-grid";
    appendTraceBlock(grid, "我现在在判断", trace.thinking);
    appendTraceList(grid, "调用 / 需要的数据节点", uniqueStrings(trace.toolPlan), "chip");
    appendTraceList(grid, "我看到的信号", trace.findings, "list");
    appendTraceBlock(grid, "当前判断", trace.judgment);
    appendTraceBlock(grid, "下一步", trace.nextStep);
    body.appendChild(grid);
    if (trace.debate) body.appendChild(renderDebate(trace.debate));
    if (output.fullText) {
      const raw = document.createElement("details");
      raw.className = "raw-section-disclosure";
      const rawSummary = document.createElement("summary");
      rawSummary.textContent = "查看原始 section markdown";
      const pre = document.createElement("pre");
      pre.className = "workflow-output-body";
      pre.textContent = output.fullText;
      raw.append(rawSummary, pre);
      body.appendChild(raw);
    }
    return body;
  }

  function appendTraceBlock(parent, title, text) {
    if (!text) return;
    const block = document.createElement("section");
    block.className = "trace-block";
    block.innerHTML = `<h3>${escapeHtml(title)}</h3><p>${escapeHtml(text)}</p>`;
    parent.appendChild(block);
  }

  function appendTraceList(parent, title, items, mode) {
    const values = uniqueStrings(items).slice(0, mode === "chip" ? 6 : 4);
    if (!values.length) return;
    const block = document.createElement("section");
    block.className = "trace-block";
    const heading = document.createElement("h3");
    heading.textContent = title;
    block.appendChild(heading);
    if (mode === "chip") {
      const row = document.createElement("div");
      row.className = "trace-chip-row";
      values.forEach((value) => {
        const chip = document.createElement("span");
        chip.className = "trace-chip";
        chip.textContent = value;
        row.appendChild(chip);
      });
      block.appendChild(row);
    } else {
      const list = document.createElement("ul");
      list.className = "trace-finding-list";
      values.forEach((value) => {
        const item = document.createElement("li");
        item.textContent = value;
        list.appendChild(item);
      });
      block.appendChild(list);
    }
    parent.appendChild(block);
  }

  function renderDebate(debate) {
    const wrap = document.createElement("section");
    wrap.className = "debate-trace";
    const heading = document.createElement("h3");
    heading.textContent = "反方审查";
    const grid = document.createElement("div");
    grid.className = "debate-grid";
    [
      ["木头姐视角", debate.cathieWood || debate.wood],
      ["巴菲特视角", debate.buffett],
      ["综合判断", debate.synthesis || debate.judgment]
    ].forEach(([title, text]) => {
      if (!text) return;
      const card = document.createElement("article");
      card.className = "debate-card";
      card.innerHTML = `<h4>${escapeHtml(title)}</h4><p>${escapeHtml(text)}</p>`;
      grid.appendChild(card);
    });
    wrap.append(heading, grid);
    return wrap;
  }

  function makePreview(text) {
    const compact = String(text || "").replace(/\s+/g, " ").trim();
    return compact.length > 96 ? `${compact.slice(0, 96)}...` : compact;
  }

  function toStringList(value) {
    if (!value) return [];
    if (Array.isArray(value)) return value.map((item) => (typeof item === "string" ? item : firstString(item, ["label", "name", "title", "summary", "text"]))).filter(Boolean);
    if (typeof value === "string") {
      return value.split(/\n|;|；|、/).map((item) => item.replace(/^[-*]\s*/, "").trim()).filter(Boolean);
    }
    return [];
  }

  function uniqueStrings(values) {
    const seen = new Set();
    return toStringList(values).filter((value) => {
      const key = String(value).trim().toLowerCase();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function inferTraceNodes(text) {
    return TRACE_NODE_PATTERNS
      .filter(([, pattern]) => pattern.test(text || ""))
      .map(([label]) => label);
  }

  function extractTraceFindings(text) {
    return String(text || "")
      .split(/\n+/)
      .map((line) => line.replace(/^[-*#\s]+/, "").trim())
      .filter((line) => line && line.length >= 8)
      .slice(0, 4);
  }

  function inferDebate(agent, text) {
    if (!/Reflection|反方|Wood|Buffett|巴菲特|木头姐/i.test(`${agent} ${text || ""}`)) return null;
    return {
      cathieWood: "关注长期创新曲线是否仍在加速，以及市场是否低估新技术扩散。",
      buffett: "检查估值、现金流和可验证护城河，避免只用故事替代证据。",
      synthesis: "只有当长期叙事、财务传导和价格行为互相印证时，才保留为高优先级观察。"
    };
  }

  function renderWorkflow(activeStep, failed) {
    state.activeStep = activeStep;
    els.workflowList.innerHTML = WORKFLOW_STEPS.map(([title, detail], index) => {
      let className = "workflow-step";
      if (failed && index === activeStep) className += " is-error";
      else if (index < activeStep) className += " is-done";
      else if (index === activeStep) className += " is-active";
      return `
        <li class="${className}">
          <span class="step-dot" aria-hidden="true"></span>
          <span><strong>${escapeHtml(title)}</strong><span>${escapeHtml(detail)}</span></span>
        </li>
      `;
    }).join("");
  }

  function updateStage(stageText) {
    if (!stageText) return;
    const normalized = String(stageText).toLowerCase();
    const matchedIndex = WORKFLOW_STEPS.findIndex(([title]) => normalized.includes(title.toLowerCase()));
    if (/运行失败|后端运行失败|failed|error|exception|timeout|超时/i.test(stageText)) {
      renderWorkflow(state.activeStep, true);
    } else if (matchedIndex >= 0) {
      renderWorkflow(matchedIndex);
    }
    appendLog(stageText);
  }

  function appendLog(line) {
    const text = String(line || "").trim();
    if (!text) return;
    state.streamLines.push(text);
    els.streamLog.textContent = state.streamLines.join("\n");
    els.streamLog.scrollTop = els.streamLog.scrollHeight;
  }

  function isStreamingResponse(contentType) {
    return /text\/event-stream|application\/x-ndjson|application\/jsonl/i.test(contentType);
  }

  async function readWholeResponse(response, contentType) {
    if (/application\/json/i.test(contentType)) return response.json();
    const text = await response.text();
    try {
      return JSON.parse(text);
    } catch (_error) {
      return text;
    }
  }

  async function readStreamingResponse(response, contentType) {
    if (!response.body) return;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let streamDone = false;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (consumeStreamLine(line, contentType)) {
          streamDone = true;
          break;
        }
      }
      if (streamDone) {
        await reader.cancel().catch(() => {});
        break;
      }
    }
    if (!streamDone && buffer.trim()) consumeStreamLine(buffer, contentType);
  }

  function consumeStreamLine(line, contentType) {
    const trimmed = line.trim();
    if (!trimmed) return false;
    let dataLine = trimmed;
    if (/text\/event-stream/i.test(contentType)) {
      if (!trimmed.startsWith("data:")) return false;
      dataLine = trimmed.replace(/^data:\s*/, "");
    }
    if (dataLine === "[DONE]") return true;
    try {
      mergeStreamEvent(JSON.parse(dataLine));
    } catch (_error) {
      state.partialMarkdown += `${dataLine}\n`;
      appendLog("接收 Markdown 内容...");
    }
    return false;
  }

  function mergeStreamEvent(event) {
    if (!event || typeof event !== "object") return;
    state.streamObject = deepMerge(state.streamObject, event);
    const stage = firstString(event, ["stage", "status", "step", "message", "event"]);
    if (stage) updateStage(stage);
    recordWorkflowOutputEvent(event, stage);
    const preview = firstString(event, ["preview", "excerpt"]);
    if (preview) appendLog(preview);
    const delta = firstString(event, ["delta", "content_delta", "chunk", "text_delta"]);
    if (delta) {
      state.partialMarkdown += delta;
      appendLog("接收报告片段...");
    }
    const markdown = firstString(event, ["markdown", "reportMarkdown", "report_markdown", "content"]);
    if (markdown && markdown.length > state.partialMarkdown.length) state.partialMarkdown = markdown;
  }

  function recordWorkflowOutputEvent(event, stage) {
    const eventName = firstString(event, ["event"]);
    const agent = firstString(event, ["agent", "section", "sectionName"]) || inferAgentFromStage(stage);
    const sectionMarkdown = firstString(event, ["sectionMarkdown", "section_markdown"]);
    const explicitOutput = firstString(event, ["output", "content", "text"]);
    const decision = firstString(event, ["decision", "decisions", "rationale", "thinkingSummary", "thinking_summary", "reasoningSummary", "reasoning_summary"]);
    const preview = firstString(event, ["preview", "excerpt", "summary", "status", "message", "error"]);
    const trace = event.thinkingTrace || event.thinking_trace || event.agentTrace || event.agent_trace || event.trace || null;
    if (/agent_start|run_start|final_payload_start|final_payload_done/i.test(eventName)) return;
    if (/run_error/i.test(eventName)) {
      const message = preview || stage || "工作流运行失败";
      addWorkflowOutput({ agent: "Workflow Error", stage: "failed", preview: message, fullText: [message, sectionMarkdown || explicitOutput].filter(Boolean).join("\n\n") });
      return;
    }
    if (/run_done/i.test(eventName) && !sectionMarkdown && !explicitOutput && !decision && !preview && !trace) return;
    const fullText = [sectionMarkdown || explicitOutput, decision].filter(Boolean).join("\n\n");
    if (fullText || preview || trace) addWorkflowOutput({ agent, stage: stage || eventName || "输出", preview: preview || makePreview(fullText), fullText, trace });
  }

  function inferAgentFromStage(stage) {
    const text = String(stage || "").trim();
    const matched = WORKFLOW_STEPS.find(([title]) => text.toLowerCase().includes(title.toLowerCase()));
    return matched ? matched[0] : text.replace(/\s*(开始|完成|start|done)$/i, "").trim() || "Workflow";
  }

  function normalizeApiPayload(payload, fallbackMarkdown) {
    const normalized = {
      raw: payload,
      title: "周报已生成",
      reportMarkdown: "",
      summaryMarkdown: "",
      evidenceMarkdown: "",
      researchActionPool: [],
      agentTrace: [],
      files: [],
      urls: {}
    };
    if (typeof payload === "string") {
      normalized.reportMarkdown = payload;
    } else if (payload && typeof payload === "object") {
      normalized.title = firstString(payload, ["title", "report_title", "name"]) || normalized.title;
      normalized.files = collectFiles(payload);
      normalized.researchActionPool = collectResearchActionPool(payload);
      normalized.agentTrace = collectAgentTrace(payload);
      normalized.reportMarkdown =
        firstString(payload, ["markdown", "reportMarkdown", "report_markdown", "fullMarkdown", "full_markdown", "finalMarkdown", "final_markdown", "md", "content"]) ||
        markdownFromFiles(normalized.files, /(^|[./-])(report|weekly|brief|final).*\.md$/i, /evidence/i);
      normalized.summaryMarkdown =
        firstString(payload, ["summaryMarkdown", "summary_markdown", "shortMarkdown", "short_markdown", "briefMarkdown", "brief_markdown", "summary"]) ||
        markdownFromFiles(normalized.files, /(summary|short|brief).*\.md$/i, /evidence/i);
      normalized.evidenceMarkdown =
        firstString(payload, ["evidenceMarkdown", "evidence_markdown", "evidencePackMarkdown", "evidence_pack_markdown", "evidencePack", "evidence_pack"]) ||
        markdownFromFiles(normalized.files, /evidence.*\.md$/i);
      normalized.urls = collectUrls(payload, normalized.files);
    }
    if (!normalized.reportMarkdown && fallbackMarkdown) normalized.reportMarkdown = fallbackMarkdown;
    if (!normalized.reportMarkdown) normalized.reportMarkdown = "API 已返回，但前端没有找到 Markdown 字段。请检查响应是否包含 markdown、reportMarkdown、files[].content 或 text/plain。";
    if (!normalized.summaryMarkdown) normalized.summaryMarkdown = extractSummaryMarkdown(normalized.reportMarkdown);
    if (!normalized.evidenceMarkdown) normalized.evidenceMarkdown = buildEvidenceMarkdown(normalized.reportMarkdown, normalized.urls);
    if (!normalized.researchActionPool.length) normalized.researchActionPool = parseResearchActionPoolFromMarkdown(normalized.reportMarkdown);
    return normalized;
  }

  function collectFiles(value) {
    const files = [];
    const seen = new Set();
    function visit(node) {
      if (!node || typeof node !== "object") return;
      if (Array.isArray(node)) return node.forEach(visit);
      const name = firstString(node, ["name", "filename", "fileName", "path", "title"]);
      const content = firstString(node, ["content", "markdown", "text", "body"]);
      const url = firstString(node, ["url", "downloadUrl", "download_url", "href"]);
      if ((name || url) && (content || url)) {
        const key = `${name}|${url}|${content.slice(0, 40)}`;
        if (!seen.has(key)) {
          seen.add(key);
          files.push({ name: name || url || "artifact.md", content: content || "", url: url || "" });
        }
      }
      Object.keys(node).forEach((key) => {
        if (/files|artifacts|outputs|attachments|documents/i.test(key)) visit(node[key]);
      });
    }
    visit(value);
    return files;
  }

  function collectAgentTrace(payload) {
    if (!payload || typeof payload !== "object") return [];
    const direct = payload.agentTrace || payload.agent_trace || payload.thinkingTrace || payload.thinking_trace;
    if (Array.isArray(direct)) return direct.filter((item) => item && typeof item === "object");
    const traces = [];
    const seen = new Set();
    function visit(node) {
      if (!node || typeof node !== "object" || seen.has(node)) return;
      seen.add(node);
      if (Array.isArray(node)) {
        node.forEach(visit);
        return;
      }
      Object.entries(node).forEach(([key, value]) => {
        if (/agentTrace|thinkingTrace/i.test(key) && Array.isArray(value)) {
          value.forEach((item) => {
            if (item && typeof item === "object") traces.push(item);
          });
          return;
        }
        if (value && typeof value === "object") visit(value);
      });
    }
    visit(payload);
    return traces;
  }

  function collectUrls(payload, files) {
    const urls = {};
    if (payload && typeof payload === "object") {
      urls.report = firstNestedString(payload, [/report.*url/i, /download.*url/i]);
      urls.evidence = firstNestedString(payload, [/evidence.*url/i]);
    }
    files.forEach((file) => {
      if (!file.url) return;
      if (/evidence/i.test(file.name)) urls.evidence = file.url;
      else if (/\.md($|[?#])/i.test(file.name) || /\.md($|[?#])/i.test(file.url)) urls.report = file.url;
    });
    return urls;
  }

  function markdownFromFiles(files, includeRegex, excludeRegex) {
    const file = files.find((item) => item.content && includeRegex.test(item.name || "") && (!excludeRegex || !excludeRegex.test(item.name || "")));
    return file ? file.content : "";
  }

  function collectResearchActionPool(payload) {
    if (!payload || typeof payload !== "object") return [];
    const direct = payload.researchActionPool || payload.research_action_pool || payload.top5 || payload.top_5 || payload.candidates;
    if (!Array.isArray(direct)) return [];
    return direct.map((item, index) => normalizeCandidate(item, index)).filter((item) => item.ticker);
  }

  function normalizeCandidate(item, index = 0) {
    const candidate = {
      runId: firstString(item, ["runId", "run_id"]) || runMetadataRunId(),
      decisionDate: firstString(item, ["decisionDate", "decision_date"]) || todayDateString(),
      thesisId: firstString(item, ["thesisId", "thesis_id"]),
      rank: item && (item.rank || item.Rank) ? item.rank || item.Rank : index + 1,
      ticker: normalizeTicker(firstString(item, ["ticker", "symbol", "tickerTheme", "ticker_theme"])),
      company: firstString(item, ["company", "name"]),
      actionRating: firstString(item, ["actionRating", "action_rating", "rating"]),
      confidence: numberOrNull(item && item.confidence),
      estimatedUpsideLowPct: numberOrNull(item && (item.estimatedUpsideLowPct ?? item.estimated_upside_low_pct)),
      estimatedUpsideBasePct: numberOrNull(item && (item.estimatedUpsideBasePct ?? item.estimated_upside_base_pct)),
      estimatedUpsideHighPct: numberOrNull(item && (item.estimatedUpsideHighPct ?? item.estimated_upside_high_pct)),
      estimatedHoldingMinDays: numberOrNull(item && (item.estimatedHoldingMinDays ?? item.estimated_holding_min_days)),
      estimatedHoldingMaxDays: numberOrNull(item && (item.estimatedHoldingMaxDays ?? item.estimated_holding_max_days)),
      exitOrTrimRule: firstString(item, ["exitOrTrimRule", "exit_or_trim_rule", "exitOrTrimBias", "exit_or_trim_bias"]),
      invalidationCondition: firstString(item, ["invalidationCondition", "invalidation_condition", "invalidation"]),
      thesisSummary: firstString(item, ["thesisSummary", "thesis_summary", "summary"]),
      hardEvidence: firstString(item, ["hardEvidence", "hard_evidence", "hardEvidenceSummary", "hard_evidence_summary"]),
      whyNow: firstString(item, ["whyNow", "why_now"]),
      nextWeekCheck: firstString(item, ["nextWeekCheck", "next_week_check"]),
      evidencePackHref: firstString(item, ["evidencePackHref", "evidence_pack_href", "evidencePack", "evidence_pack"]),
      benchmarkPrimary: firstString(item, ["benchmarkPrimary", "benchmark_primary"]) || "QQQ"
    };
    if (!candidate.thesisId) candidate.thesisId = `${candidate.ticker || "candidate"}-${candidate.rank}`;
    return candidate;
  }

  function parseResearchActionPoolFromMarkdown(markdown) {
    const lines = String(markdown || "").split(/\r?\n/);
    for (let index = 0; index < lines.length; index += 1) {
      if (!/^#{1,4}\s+.*(Top\s*5\s*Research\s*Action\s*Pool|本周研究动作)/i.test(lines[index].trim())) continue;
      for (let tableIndex = index + 1; tableIndex < Math.min(index + 24, lines.length); tableIndex += 1) {
        if (!lines[tableIndex].includes("|") || !isMarkdownSeparator(lines[tableIndex + 1] || "")) continue;
        const headers = splitMarkdownRow(lines[tableIndex]).map(normalizeTableHeader);
        const rows = [];
        for (let rowIndex = tableIndex + 2; rowIndex < lines.length; rowIndex += 1) {
          const line = lines[rowIndex];
          if (!line.includes("|") || line.trim().startsWith("#")) break;
          const cells = splitMarkdownRow(line);
          const raw = {};
          headers.forEach((header, cellIndex) => {
            raw[header] = cells[cellIndex] || "";
          });
          const candidate = candidateFromMarkdownRow(raw, rows.length);
          if (candidate.ticker) rows.push(candidate);
        }
        if (rows.length) return rows.slice(0, 5);
      }
    }
    return [];
  }

  function candidateFromMarkdownRow(raw, index) {
    const tickerText = markdownPlainText(raw.ticker || "");
    const ticker = normalizeTicker(tickerText);
    const company = tickerText.replace(ticker, "").replace(/^[-/()：:\s]+/, "").trim();
    const upside = extractNumbers(raw.estimatedUpsideRange || "");
    const holding = extractNumbers(raw.estimatedHoldingRange || "");
    return normalizeCandidate({
      runId: runMetadataRunId(),
      decisionDate: todayDateString(),
      thesisId: `${ticker || "candidate"}-${raw.rank || index + 1}`,
      rank: raw.rank || index + 1,
      ticker,
      company,
      actionRating: markdownPlainText(raw.actionRating || ""),
      confidence: numberOrNull(raw.confidence),
      estimatedUpsideLowPct: numberOrNull(upside[0]),
      estimatedUpsideBasePct: numberOrNull(upside[1]),
      estimatedUpsideHighPct: numberOrNull(upside[2]),
      estimatedHoldingMinDays: numberOrNull(holding[0]),
      estimatedHoldingMaxDays: numberOrNull(holding[1] || holding[0]),
      exitOrTrimRule: markdownPlainText(raw.exitOrTrimRule || ""),
      invalidationCondition: markdownPlainText(raw.invalidationCondition || ""),
      thesisSummary: tickerText,
      hardEvidence: markdownPlainText(raw.hardEvidence || ""),
      whyNow: markdownPlainText(raw.whyNow || ""),
      nextWeekCheck: markdownPlainText(raw.nextWeekCheck || ""),
      evidencePackHref: markdownHref(raw.evidencePack || "") || markdownPlainText(raw.evidencePack || ""),
      benchmarkPrimary: "QQQ"
    }, index);
  }

  function normalizeTableHeader(value) {
    const header = markdownPlainText(value).toLowerCase();
    if (/rank|排名|序号/.test(header)) return "rank";
    if (/ticker|theme|公司|主题/.test(header)) return "ticker";
    if (/rating|动作/.test(header)) return "actionRating";
    if (/confidence|置信/.test(header)) return "confidence";
    if (/upside|涨幅/.test(header)) return "estimatedUpsideRange";
    if (/holding|观察|周期/.test(header)) return "estimatedHoldingRange";
    if (/exit|trim|止盈/.test(header)) return "exitOrTrimRule";
    if (/why now|为什么/.test(header)) return "whyNow";
    if (/hard evidence|证据摘要/.test(header)) return "hardEvidence";
    if (/evidence pack|证据包/.test(header)) return "evidencePack";
    if (/falsification|invalidation|反证|失效/.test(header)) return "invalidationCondition";
    if (/next|下周/.test(header)) return "nextWeekCheck";
    return header.replace(/\W+/g, "_");
  }

  function splitMarkdownRow(line) {
    return String(line || "").trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
  }

  function isMarkdownSeparator(line) {
    const cells = splitMarkdownRow(line);
    return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
  }

  function completeRun(result) {
    state.view = "result";
    state.result = result;
    setTopbarMode("detail");
    els.cancelButton.hidden = true;
    els.cancelButton.disabled = true;
    renderWorkflow(WORKFLOW_STEPS.length);
    completeRunProgress();
    appendLog("完成。");
    els.workspace.hidden = true;
    els.result.hidden = false;
    els.reportHistory.hidden = true;
    els.pond.hidden = true;
    els.resultTitle.textContent = result.title || "周报已生成";
    els.resultMeta.textContent = resultHistoryMeta(result);
    renderMarkdown(result.summaryMarkdown, els.panelSummary);
    renderMarkdown(result.reportMarkdown, els.panelReport);
    renderMarkdown(result.evidenceMarkdown, els.panelEvidence);
    els.rawMarkdown.textContent = result.reportMarkdown;
    renderResultAgentTrace(result);
    renderCandidatePool(result.researchActionPool || []);
    loadPondData({ quiet: true });
    loadReportHistory({ quiet: true });
    switchTab("summary");
    els.result.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function resultHistoryMeta(result) {
    const metadata = result && result.raw && typeof result.raw.runMetadata === "object" ? result.raw.runMetadata : {};
    const status = reportStatusLabel(reportStatusFromPayload(result || {}));
    if (metadata.historyId) return `${status} · 已保存到历史记录`;
    return `${status} · 当前后端未返回历史编号，报告仍可在本页下载`;
  }

  function renderResultAgentTrace(result) {
    if (state.workflowOutputs.length || !result || !Array.isArray(result.agentTrace)) return;
    result.agentTrace.forEach((trace) => {
      const fullText = firstString(trace, ["sectionMarkdown", "section_markdown", "markdown", "content", "text"]);
      addWorkflowOutput({
        agent: firstString(trace, ["agent", "section", "sectionName"]) || "Workflow",
        stage: firstString(trace, ["status", "stage", "step"]) || "完成",
        preview: firstString(trace, ["headline", "summary", "preview"]) || makePreview(fullText),
        fullText,
        trace
      });
    });
  }

  async function loadReportHistory({ quiet }) {
    const url = makeReportHistoryUrl("/api/reports");
    try {
      const response = await fetch(url, { headers: authHeaders() });
      if (!response.ok) throw new Error(`API ${response.status}: ${response.statusText}`);
      state.reportHistoryData = normalizeReportHistoryPayload(await response.json());
      if (!state.selectedReportId && state.reportHistoryData.items.length) {
        state.selectedReportId = state.reportHistoryData.items[0].id;
      }
      if (!state.reportHistoryData.items.some((item) => item.id === state.selectedReportId)) {
        state.selectedReportId = state.reportHistoryData.items[0] ? state.reportHistoryData.items[0].id : "";
      }
      renderReportHistoryShell();
      if (state.view === "history" && state.selectedReportId) selectReportHistory(state.selectedReportId, { keepList: true });
    } catch (error) {
      if (!quiet || state.view === "history") renderReportHistoryError(friendlyApiError(error, url));
    }
  }

  function normalizeReportHistoryPayload(payload) {
    const summary = payload && payload.summary && typeof payload.summary === "object" ? payload.summary : {};
    return {
      summary: {
        count: Number(summary.count || 0),
        storage: summary.storage || ""
      },
      items: Array.isArray(payload && payload.items)
        ? payload.items.map((item) => ({
            id: String(item.id || ""),
            createdAt: String(item.createdAt || ""),
            title: String(item.title || "未命名报告"),
            status: String(item.status || "unknown"),
            source: String(item.source || ""),
            prompt: String(item.prompt || ""),
            model: String(item.model || ""),
            summaryExcerpt: String(item.summaryExcerpt || ""),
            historyPath: String(item.historyPath || "")
          })).filter((item) => item.id)
        : []
    };
  }

  function renderReportHistoryShell() {
    const data = state.reportHistoryData || normalizeReportHistoryPayload({});
    els.reportHistoryCount.textContent = `${data.summary.count || data.items.length} 条历史记录`;
    renderReportHistoryList(data.items);
    if (!state.selectedReportId) renderReportHistoryDetail(null);
  }

  function renderReportHistoryList(items) {
    if (!items.length) {
      els.reportHistoryList.innerHTML = '<div class="empty-state">暂无报告历史。生成一次周报后会自动保存。</div>';
      renderReportHistoryDetail(null);
      return;
    }
    els.reportHistoryList.innerHTML = "";
    items.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `report-history-item${item.id === state.selectedReportId ? " is-active" : ""}`;
      button.innerHTML = `
        <span class="history-item-title">${escapeHtml(item.title)}</span>
        <span class="history-item-meta">
          <span class="status-pill ${reportStatusClass(item.status)}">${escapeHtml(reportStatusLabel(item.status))}</span>
          <span>${escapeHtml(formatHistoryTime(item.createdAt))}</span>
        </span>
        <span class="history-item-prompt">${escapeHtml(item.prompt || item.summaryExcerpt || "无提示词记录")}</span>
      `;
      button.addEventListener("click", () => selectReportHistory(item.id));
      els.reportHistoryList.appendChild(button);
    });
  }

  async function selectReportHistory(id, options = {}) {
    state.selectedReportId = id;
    if (!options.keepList && state.reportHistoryData) renderReportHistoryList(state.reportHistoryData.items);
    const url = makeReportHistoryUrl(`/api/reports/${encodeURIComponent(id)}`);
    els.reportHistoryDetailTitle.textContent = "读取报告中";
    els.reportHistoryDetailMeta.textContent = "正在读取历史详情...";
    els.reportHistoryDetailBody.innerHTML = '<p class="empty-copy">正在读取...</p>';
    try {
      const response = await fetch(url, { headers: authHeaders() });
      if (!response.ok) throw new Error(`API ${response.status}: ${response.statusText}`);
      renderReportHistoryDetail(await response.json());
    } catch (error) {
      renderReportHistoryDetail({
        title: "历史记录读取失败",
        status: "failed",
        createdAt: "",
        prompt: "",
        payload: {
          reportMarkdown: `# 历史记录读取失败\n\n${friendlyApiError(error, url)}`,
          summaryMarkdown: "",
          evidenceMarkdown: ""
        }
      });
    }
  }

  function renderReportHistoryDetail(record) {
    if (!record) {
      els.reportHistoryDetailTitle.textContent = "选择一份报告";
      els.reportHistoryDetailMeta.textContent = "每次成功生成、部分生成或失败生成的报告都会保存在这里。";
      els.reportHistoryDetailBody.innerHTML = '<p class="empty-copy">点击左侧历史记录后查看精简版、完整周报和双跳证据。</p>';
      return;
    }
    const payload = normalizeApiPayload(record.payload || {});
    const status = record.status || reportStatusFromPayload(payload);
    els.reportHistoryDetailTitle.textContent = record.title || payload.title || "未命名报告";
    els.reportHistoryDetailMeta.textContent = [
      formatHistoryTime(record.createdAt),
      reportStatusLabel(status),
      record.source || "",
      record.model || ""
    ].filter(Boolean).join(" · ");
    const promptBlock = record.prompt ? `> 研究意图：${record.prompt}` : "> 研究意图：未记录";
    const markdown = [
      `# ${record.title || payload.title || "未命名报告"}`,
      promptBlock,
      `## 精简版\n${payload.summaryMarkdown || "无精简版内容。"}`,
      `## 完整周报\n${payload.reportMarkdown || "无完整周报内容。"}`,
      `## 双跳证据\n${payload.evidenceMarkdown || "无证据链内容。"}`
    ].join("\n\n");
    renderMarkdown(markdown, els.reportHistoryDetailBody);
  }

  function renderReportHistoryError(message) {
    els.reportHistoryCount.textContent = "历史记录不可用";
    els.reportHistoryList.innerHTML = `<div class="error-state">${escapeHtml(message)}</div>`;
    els.reportHistoryDetailTitle.textContent = "报告历史不可用";
    els.reportHistoryDetailMeta.textContent = "";
    els.reportHistoryDetailBody.innerHTML = `<div class="error-state">${escapeHtml(message)}</div>`;
  }

  function reportStatusFromPayload(payload) {
    const text = `${payload.title || ""} ${payload.reportMarkdown || ""}`;
    if (/研究未完成|后端运行失败|failed/i.test(text)) return "failed";
    if (/partial|缺口|未接入|数据节点不足/i.test(text)) return "partial";
    return "complete";
  }

  function reportStatusLabel(status) {
    if (/failed/i.test(status)) return "失败";
    if (/partial/i.test(status)) return "部分完成";
    if (/complete|success/i.test(status)) return "完成";
    return status || "未知";
  }

  function reportStatusClass(status) {
    if (/failed/i.test(status)) return "is-danger";
    if (/partial/i.test(status)) return "is-warn";
    if (/complete|success/i.test(status)) return "is-good";
    return "";
  }

  function formatHistoryTime(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${formatClockTime(date)}`;
  }

  async function loadPondData({ quiet }) {
    const url = makePondUrl("/api/pond");
    try {
      const response = await fetch(url, { headers: authHeaders() });
      if (!response.ok) throw new Error(`API ${response.status}: ${response.statusText}`);
      state.pondData = normalizePondPayload(await response.json());
      refreshSelectedCandidateKeys();
      renderPondPreview();
      if (state.view === "pond") renderPondPage();
      if (state.result) renderCandidatePool(state.result.researchActionPool || []);
    } catch (error) {
      renderPondPreview(quiet ? "后端未连接，池塘暂不可用" : `池塘读取失败：${friendlyApiError(error, url)}`);
      if (!quiet && state.view === "pond") renderPondError(friendlyApiError(error, url));
    }
  }

  async function refreshPondPrices() {
    const url = makePondUrl("/api/pond/refresh");
    els.pondRefreshButton.disabled = true;
    els.pondRefreshButton.textContent = "刷新中";
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ source: "frontend_pond" })
      });
      if (!response.ok) throw new Error(`API ${response.status}: ${await response.text().catch(() => response.statusText)}`);
      state.pondData = normalizePondPayload(await response.json());
      refreshSelectedCandidateKeys();
      renderPondPreview();
      renderPondPage();
    } catch (error) {
      renderPondError(friendlyApiError(error, url));
    } finally {
      els.pondRefreshButton.disabled = false;
      els.pondRefreshButton.textContent = "刷新收盘价";
    }
  }

  async function selectCandidate(candidate, button) {
    const url = makePondUrl("/api/pond/select");
    button.disabled = true;
    button.textContent = "加入中";
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ candidate })
      });
      if (!response.ok) throw new Error(`API ${response.status}: ${await response.text().catch(() => response.statusText)}`);
      state.pondData = normalizePondPayload(await response.json());
      refreshSelectedCandidateKeys();
      renderPondPreview();
      renderCandidatePool(state.result ? state.result.researchActionPool || [] : []);
    } catch (error) {
      button.disabled = false;
      button.textContent = "加入池塘";
      button.title = friendlyApiError(error, url);
    }
  }

  function normalizePondPayload(payload) {
    const summary = payload && payload.summary && typeof payload.summary === "object" ? payload.summary : {};
    return {
      summary: {
        openCount: Number(summary.openCount || 0),
        historyCount: Number(summary.historyCount || 0),
        recentTickers: Array.isArray(summary.recentTickers) ? summary.recentTickers.filter(Boolean) : [],
        latestRefreshDate: summary.latestRefreshDate || "",
        storage: summary.storage || ""
      },
      openItems: Array.isArray(payload && payload.openItems) ? payload.openItems.map(normalizePondItem) : [],
      historyGroups: Array.isArray(payload && payload.historyGroups)
        ? payload.historyGroups.map((group) => ({
            decisionDate: group.decisionDate || "unknown",
            items: Array.isArray(group.items) ? group.items.map(normalizePondItem) : []
          }))
        : []
    };
  }

  function normalizePondItem(item) {
    const normalized = { ...(item || {}) };
    normalized.id = normalized.id || candidateKey(normalized);
    normalized.ticker = normalizeTicker(normalized.ticker || "");
    ["actualReturnPct", "benchmarkReturnPct", "excessReturnPct", "actualEntryPrice", "reviewExitPrice", "estimatedUpsideLowPct", "estimatedUpsideBasePct", "estimatedUpsideHighPct"].forEach((key) => {
      normalized[key] = numberOrNull(normalized[key]);
    });
    return normalized;
  }

  function refreshSelectedCandidateKeys() {
    const keys = new Set();
    if (state.pondData) {
      state.pondData.openItems.forEach((item) => keys.add(candidateKey(item)));
      state.pondData.historyGroups.forEach((group) => group.items.forEach((item) => keys.add(candidateKey(item))));
    }
    state.selectedCandidateKeys = keys;
  }

  function renderPondPreview(errorText) {
    if (errorText) {
      els.pondPreviewMeta.textContent = errorText;
      els.pondPreviewTickers.innerHTML = "";
      return;
    }
    const summary = state.pondData && state.pondData.summary;
    if (!summary) {
      els.pondPreviewMeta.textContent = "池塘暂时没有数据";
      els.pondPreviewTickers.innerHTML = "";
      return;
    }
    els.pondPreviewMeta.textContent = `${summary.openCount} 个近期关注 · ${summary.latestRefreshDate ? `最近刷新 ${summary.latestRefreshDate}` : "尚未刷新收盘价"}`;
    els.pondPreviewTickers.innerHTML = summary.recentTickers.length
      ? summary.recentTickers.map((ticker) => `<span class="ticker-pill">${escapeHtml(ticker)}</span>`).join("")
      : '<span class="ticker-pill">空池塘</span>';
  }

  function renderCandidatePool(candidates) {
    const pool = (candidates || []).map((candidate, index) => normalizeCandidate(candidate, index)).filter((candidate) => candidate.ticker);
    els.candidateSection.hidden = pool.length === 0;
    if (!pool.length) {
      els.candidateGrid.innerHTML = "";
      return;
    }
    els.candidateStatus.textContent = `${pool.length} 个候选`;
    els.candidateGrid.innerHTML = "";
    pool.forEach((candidate, index) => {
      const card = document.createElement("article");
      card.className = "candidate-card";
      const selected = state.selectedCandidateKeys.has(candidateKey(candidate));
      card.innerHTML = `
        <header>
          <div><strong>${escapeHtml(candidate.ticker)}</strong><small>${escapeHtml(candidate.company || candidate.thesisSummary || "本周候选")}</small></div>
          <span class="status-pill">${escapeHtml(candidate.actionRating || "No Rating")}</span>
        </header>
        <div class="candidate-metrics">
          ${metricBox("置信度", formatPercent(candidate.confidence))}
          ${metricBox("预估", formatRange(candidate.estimatedUpsideLowPct, candidate.estimatedUpsideBasePct, candidate.estimatedUpsideHighPct, "%"))}
          ${metricBox("观察", formatHolding(candidate))}
        </div>
        <p>${escapeHtml(candidate.whyNow || candidate.hardEvidence || candidate.thesisSummary || "等待报告补充 why now。")}</p>
      `;
      const button = document.createElement("button");
      button.className = selected ? "secondary-button compact-button" : "primary-button compact-button";
      button.type = "button";
      button.textContent = selected ? "已在池塘" : "加入池塘";
      button.disabled = selected;
      button.addEventListener("click", () => selectCandidate({ ...candidate, rank: candidate.rank || index + 1 }, button));
      card.appendChild(button);
      els.candidateGrid.appendChild(card);
    });
  }

  function renderPondPage() {
    const data = state.pondData || normalizePondPayload({});
    const openItems = data.openItems;
    els.pondOpenCount.textContent = `${openItems.length} 个`;
    els.pondHistoryCount.textContent = `${data.summary.historyCount || 0} 条`;
    els.pondLastRefresh.textContent = data.summary.latestRefreshDate ? `最新可用收盘价：${data.summary.latestRefreshDate}` : "最新可用收盘价：尚未刷新";
    if (!state.selectedPondId && openItems.length) state.selectedPondId = openItems[0].id;
    if (!openItems.some((item) => item.id === state.selectedPondId)) state.selectedPondId = openItems[0] ? openItems[0].id : "";
    renderPondOpenTable(openItems);
    renderPondDetail(openItems.find((item) => item.id === state.selectedPondId));
    renderPondHistory(data.historyGroups);
  }

  function renderPondOpenTable(items) {
    if (!items.length) {
      els.pondOpenTable.innerHTML = '<tr><td colspan="4" class="empty-copy">还没有近期关注。周报生成后，在“本周候选”里点加入池塘。</td></tr>';
      return;
    }
    els.pondOpenTable.innerHTML = "";
    items.forEach((item) => {
      const row = document.createElement("tr");
      const active = item.id === state.selectedPondId;
      row.innerHTML = `
        <td><button class="ticker-button${active ? " is-active" : ""}" type="button">${escapeHtml(item.ticker || "-")}</button></td>
        <td>${escapeHtml(item.actionRating || "-")}</td>
        <td>${escapeHtml(formatPercent(item.actualReturnPct))}</td>
        <td><span class="status-pill ${expectedClass(item.expectedVsActual || item.status)}">${escapeHtml(expectedLabel(item.expectedVsActual || item.status))}</span></td>
      `;
      row.querySelector("button").addEventListener("click", () => {
        state.selectedPondId = item.id;
        renderPondPage();
      });
      els.pondOpenTable.appendChild(row);
    });
  }

  function renderPondDetail(item) {
    if (!item) {
      els.pondDetailTitle.textContent = "选择一个关注项";
      els.pondDetailBody.innerHTML = '<p class="empty-copy">点击左侧 ticker 后查看 thesis、收盘价和预估区间。</p>';
      return;
    }
    els.pondDetailTitle.textContent = `${item.ticker || "-"} 观察详情`;
    const evidenceLink = item.evidencePackHref ? `<a href="${escapeHtml(item.evidencePackHref)}">${escapeHtml(item.evidencePackHref)}</a>` : "暂无证据链接";
    els.pondDetailBody.innerHTML = `
      <div class="detail-title-row">
        <div><strong>${escapeHtml(item.ticker || "-")}</strong><p class="detail-copy">${escapeHtml(item.company || item.thesisSummary || "近期关注")}</p></div>
        <span class="status-pill ${expectedClass(item.expectedVsActual || item.status)}">${escapeHtml(expectedLabel(item.expectedVsActual || item.status))}</span>
      </div>
      <div class="detail-metrics">
        ${metricBox("Entry Close", formatPrice(item.actualEntryPrice))}
        ${metricBox("Latest Close", formatPrice(item.reviewExitPrice))}
        ${metricBox("涨跌幅", formatPercent(item.actualReturnPct))}
      </div>
      <div class="detail-metrics">
        ${metricBox("预估区间", formatRange(item.estimatedUpsideLowPct, item.estimatedUpsideBasePct, item.estimatedUpsideHighPct, "%"))}
        ${metricBox("Benchmark", item.benchmarkPrimary || "QQQ")}
        ${metricBox("超额", formatPercent(item.excessReturnPct))}
      </div>
      <p class="detail-copy"><strong>Thesis：</strong>${escapeHtml(item.thesisSummary || "暂无 thesis 摘要。")}</p>
      <p class="detail-copy"><strong>Why now：</strong>${escapeHtml(item.whyNow || "暂无 why now。")}</p>
      <p class="detail-copy"><strong>证据：</strong>${escapeHtml(item.hardEvidence || "暂无硬证据摘要。")}</p>
      <p class="detail-copy"><strong>失效条件：</strong>${escapeHtml(item.invalidationCondition || "暂无失效条件。")}</p>
      <p class="detail-copy"><strong>Evidence Pack：</strong>${evidenceLink}</p>
    `;
    decorateLinks(els.pondDetailBody);
  }

  function renderPondHistory(groups) {
    if (!groups.length) {
      els.pondHistoryList.innerHTML = '<div class="empty-state">暂无历史记录。关闭或归档的观察会出现在这里。</div>';
      return;
    }
    els.pondHistoryList.innerHTML = "";
    groups.forEach((group) => {
      const details = document.createElement("details");
      details.className = "history-group";
      details.open = true;
      details.innerHTML = `
        <summary><span>${escapeHtml(group.decisionDate)}</span><span>${group.items.length} 条</span></summary>
        <div class="history-items">
          ${group.items.map((item) => `
            <div class="history-item">
              <strong>${escapeHtml(item.ticker || "-")}</strong>
              <span>${escapeHtml(item.thesisSummary || item.company || "历史观察")}</span>
              <span class="status-pill ${expectedClass(item.expectedVsActual || item.status)}">${escapeHtml(expectedLabel(item.expectedVsActual || item.status))}</span>
            </div>
          `).join("")}
        </div>
      `;
      els.pondHistoryList.appendChild(details);
    });
  }

  function renderPondError(message) {
    els.pondOpenTable.innerHTML = `<tr><td colspan="4" class="error-state">${escapeHtml(message)}</td></tr>`;
    els.pondDetailTitle.textContent = "池塘暂不可用";
    els.pondDetailBody.innerHTML = `<div class="error-state">${escapeHtml(message)}</div>`;
  }

  function showRunError(message) {
    renderWorkflow(state.activeStep, true);
    els.cancelButton.hidden = true;
    els.cancelButton.disabled = true;
    els.streamLog.textContent = message;
    els.thinkingWord.textContent = "未完成";
    addMessage("assistant", "研究台", message);
    if (state.partialMarkdown.trim()) completeRun(normalizeApiPayload(state.partialMarkdown));
  }

  function switchTab(tabName) {
    const panels = {
      summary: document.getElementById("panel-summary"),
      report: document.getElementById("panel-report"),
      evidence: document.getElementById("panel-evidence"),
      raw: document.getElementById("panel-raw")
    };
    document.querySelectorAll(".tab-button").forEach((button) => {
      const isActive = button.dataset.tab === tabName;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-selected", String(isActive));
    });
    Object.keys(panels).forEach((key) => {
      const panel = panels[key];
      const isActive = key === tabName;
      panel.hidden = !isActive;
      panel.classList.toggle("is-active", isActive);
    });
  }

  function renderMarkdown(markdown, container) {
    container.innerHTML = markdownToHtml(markdown || "");
    decorateLinks(container);
  }

  function markdownToHtml(markdown) {
    const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
    const html = [];
    let listType = null;
    let inCode = false;
    let codeLines = [];
    const slugCounts = new Map();

    function closeList() {
      if (listType) html.push(`</${listType}>`);
      listType = null;
    }

    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i];
      if (/^```/.test(line.trim())) {
        if (inCode) {
          html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
          codeLines = [];
          inCode = false;
        } else {
          closeList();
          inCode = true;
        }
        continue;
      }
      if (inCode) {
        codeLines.push(line);
        continue;
      }
      if (isTableStart(lines, i)) {
        closeList();
        const table = collectTable(lines, i);
        html.push(renderTable(table.rows));
        i = table.nextIndex - 1;
        continue;
      }
      const trimmed = line.trim();
      if (!trimmed) {
        closeList();
        continue;
      }
      const heading = trimmed.match(/^(#{1,4})\s+(.+)$/);
      if (heading) {
        closeList();
        const level = heading[1].length;
        const text = heading[2].trim();
        const slug = slugify(text, slugCounts);
        html.push(`<h${level} id="${slug}">${inlineMarkdown(text)}</h${level}>`);
        continue;
      }
      const ordered = trimmed.match(/^\d+[.)]\s+(.+)$/);
      const unordered = trimmed.match(/^[-*]\s+(.+)$/);
      if (ordered || unordered) {
        const type = ordered ? "ol" : "ul";
        if (listType !== type) {
          closeList();
          html.push(`<${type}>`);
          listType = type;
        }
        html.push(`<li>${inlineMarkdown((ordered || unordered)[1])}</li>`);
        continue;
      }
      closeList();
      html.push(`<p>${inlineMarkdown(trimmed)}</p>`);
    }
    closeList();
    if (inCode) html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    return html.join("\n");
  }

  function isTableStart(lines, index) {
    return lines[index] && lines[index].includes("|") && isMarkdownSeparator(lines[index + 1] || "");
  }

  function collectTable(lines, startIndex) {
    const rows = [splitMarkdownRow(lines[startIndex])];
    let index = startIndex + 2;
    while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
      rows.push(splitMarkdownRow(lines[index]));
      index += 1;
    }
    return { rows, nextIndex: index };
  }

  function renderTable(rows) {
    if (!rows.length) return "";
    const header = rows[0].map((cell) => `<th>${inlineMarkdown(cell)}</th>`).join("");
    const body = rows.slice(1).map((row) => `<tr>${row.map((cell) => `<td>${inlineMarkdown(cell)}</td>`).join("")}</tr>`).join("");
    return `<div class="table-scroll"><table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function inlineMarkdown(value) {
    return escapeHtml(value)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
  }

  function decorateLinks(container) {
    container.querySelectorAll("a[href]").forEach((link) => {
      const href = link.getAttribute("href") || "";
      if (/^https?:\/\//i.test(href)) {
        link.target = "_blank";
        link.rel = "noopener noreferrer";
      }
      link.addEventListener("click", (event) => {
        if (href.startsWith("#")) {
          event.preventDefault();
          scrollToAnchor(container, href.slice(1));
        }
      });
    });
  }

  function scrollToAnchor(panel, hash) {
    if (!panel || !hash) return;
    const target = panel.querySelector(`#${cssEscape(decodeURIComponent(hash))}`);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function extractSummaryMarkdown(markdown) {
    const text = String(markdown || "").trim();
    if (!text) return "";
    const bossIndex = text.search(/^#\s*老板决策页/m);
    const sliced = text.slice(bossIndex >= 0 ? bossIndex : 0);
    const endPatterns = [/\n##\s*5[.．、\s]/, /\n#\s*附录/m, /\n##\s*附录/m, /\n##\s*Intent Route Plan/i, /\n##\s*Data Node Status/i];
    const ends = endPatterns.map((pattern) => sliced.search(pattern)).filter((index) => index > 0);
    return ends.length ? sliced.slice(0, Math.min(...ends)).trim() : sliced.split("\n").slice(0, 120).join("\n").trim();
  }

  function buildEvidenceMarkdown(reportMarkdown, urls) {
    const links = extractMarkdownLinks(reportMarkdown).filter((link) => /evidence|证据|source|sec|ir|github|arxiv|http/i.test(`${link.label} ${link.href}`));
    if (!links.length) return "# 双跳证据\n\nAPI 未返回独立 evidence markdown，且完整周报里没有识别到证据链接。";
    const rows = links.map((link, index) => `| E${index + 1} | Link | [${escapeMarkdownCell(link.label)}](${link.href}) | ${escapeMarkdownCell(link.href)} |`);
    if (urls && urls.evidence) rows.unshift(`| E0 | Evidence File | [Evidence](${urls.evidence}) | ${escapeMarkdownCell(urls.evidence)} |`);
    return ["# 双跳证据", "", "| ID | Source Type | Evidence Anchor | Notes |", "|---|---|---|---|", ...rows].join("\n");
  }

  function extractMarkdownLinks(markdown) {
    return [...String(markdown || "").matchAll(/\[([^\]]+)\]\(([^)]+)\)/g)].map((match) => ({ label: match[1], href: match[2] }));
  }

  function downloadMarkdown(markdown, fallbackName) {
    const blob = new Blob([markdown || ""], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = fallbackName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function firstString(object, keys) {
    if (!object || typeof object !== "object") return "";
    for (const key of keys) {
      const value = object[key];
      if (typeof value === "string" && value.trim()) return value;
      if (typeof value === "number" && Number.isFinite(value)) return String(value);
    }
    return "";
  }

  function firstNestedString(value, keyPatterns) {
    const seen = new Set();
    const queue = [value];
    while (queue.length) {
      const node = queue.shift();
      if (!node || typeof node !== "object" || seen.has(node)) continue;
      seen.add(node);
      if (Array.isArray(node)) {
        queue.push(...node);
        continue;
      }
      for (const [key, child] of Object.entries(node)) {
        if (typeof child === "string" && keyPatterns.some((pattern) => pattern.test(key))) return child;
        if (child && typeof child === "object") queue.push(child);
      }
    }
    return "";
  }

  function deepMerge(target, source) {
    const output = { ...(target || {}) };
    Object.entries(source || {}).forEach(([key, value]) => {
      if (value && typeof value === "object" && !Array.isArray(value) && output[key] && typeof output[key] === "object" && !Array.isArray(output[key])) {
        output[key] = deepMerge(output[key], value);
      } else {
        output[key] = value;
      }
    });
    return output;
  }

  function candidateKey(item) {
    return [item.runId || item.run_id || "", item.thesisId || item.thesis_id || "", item.ticker || ""]
      .map((part) => String(part).trim().toUpperCase())
      .join("|");
  }

  function metricBox(label, value) {
    return `<span class="metric-box"><span class="metric-label">${escapeHtml(label)}</span><span class="metric-value">${escapeHtml(value || "-")}</span></span>`;
  }

  function formatPercent(value) {
    if (value === null || value === undefined || value === "") return "-";
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value);
    return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
  }

  function formatPrice(value) {
    if (value === null || value === undefined || value === "") return "-";
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(2) : String(value);
  }

  function formatRange(low, base, high, suffix) {
    const parts = [low, base, high]
      .filter((value) => value !== null && value !== undefined && value !== "")
      .map((value) => `${Number(value).toFixed(Number(value) % 1 === 0 ? 0 : 1)}${suffix}`);
    return parts.length ? parts.join(" / ") : "-";
  }

  function formatHolding(candidate) {
    const min = candidate.estimatedHoldingMinDays;
    const max = candidate.estimatedHoldingMaxDays;
    if (min && max) return `${min}-${max} 天`;
    if (min || max) return `${min || max} 天`;
    return "-";
  }

  function expectedLabel(value) {
    const labels = {
      pending_entry: "等待入场收盘",
      interim_on_track: "暂时匹配",
      in_range: "落入区间",
      above_range: "超过区间",
      direction_right_below_range: "方向对但未达区间",
      direction_wrong: "方向不一致",
      price_data_failed: "价格失败",
      open: "观察中",
      candidate: "候选",
      closed: "已关闭",
      archived: "已归档"
    };
    return labels[String(value || "").toLowerCase()] || value || "-";
  }

  function expectedClass(value) {
    const key = String(value || "").toLowerCase();
    if (/in_range|above_range|interim_on_track|open/.test(key)) return "good";
    if (/pending|candidate|below/.test(key)) return "warn";
    if (/wrong|failed/.test(key)) return "danger";
    return "";
  }

  function markdownPlainText(value) {
    return String(value || "").replace(/\[([^\]]+)\]\([^)]+\)/g, "$1").replace(/`([^`]+)`/g, "$1").replace(/\s+/g, " ").trim();
  }

  function markdownHref(value) {
    const match = String(value || "").match(/\[[^\]]+\]\(([^)]+)\)/);
    return match ? match[1].trim() : "";
  }

  function extractNumbers(value) {
    return [...String(value || "").matchAll(/-?\d+(?:\.\d+)?/g)].map((match) => match[0]);
  }

  function normalizeTicker(value) {
    const text = String(value || "").toUpperCase();
    const match = text.match(/\b[A-Z][A-Z0-9.-]{0,7}\b/);
    return match ? match[0] : "";
  }

  function numberOrNull(value) {
    if (value === null || value === undefined || value === "") return null;
    const match = String(value).match(/-?\d+(?:\.\d+)?/);
    if (!match) return null;
    const number = Number(match[0]);
    return Number.isFinite(number) ? number : null;
  }

  function todayDateString() {
    return new Date().toISOString().slice(0, 10);
  }

  function runMetadataRunId() {
    const metadata = state.result && state.result.raw && state.result.raw.runMetadata;
    return (metadata && metadata.runId) || `frontend-${todayDateString()}`;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    })[char]);
  }

  function escapeMarkdownCell(value) {
    return String(value || "").replace(/\|/g, "\\|");
  }

  function slugify(value, counts) {
    const base = String(value || "section").toLowerCase().replace(/[^\w\u4e00-\u9fff]+/g, "-").replace(/^-|-$/g, "") || "section";
    const count = counts.get(base) || 0;
    counts.set(base, count + 1);
    return count ? `${base}-${count}` : base;
  }

  function cssEscape(value) {
    if (window.CSS && CSS.escape) return CSS.escape(value);
    return String(value).replace(/[^a-zA-Z0-9_-]/g, "\\$&");
  }

  function startCanvas() {
    const canvas = els.canvas;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    let frame = 0;
    function resize() {
      const scale = window.devicePixelRatio || 1;
      canvas.width = Math.floor(window.innerWidth * scale);
      canvas.height = Math.floor(window.innerHeight * scale);
      context.setTransform(scale, 0, 0, scale, 0, 0);
    }
    function draw() {
      const width = window.innerWidth;
      const height = window.innerHeight;
      context.clearRect(0, 0, width, height);
      context.strokeStyle = "rgba(98, 183, 255, 0.17)";
      context.lineWidth = 1.5;
      for (let i = 0; i < 5; i += 1) {
        context.beginPath();
        const offset = (frame * 0.15 + i * 90) % 240;
        context.arc(width / 2, height + 220 + offset, width * (0.62 + i * 0.12), Math.PI * 1.05, Math.PI * 1.95);
        context.stroke();
      }
      context.strokeStyle = "rgba(114, 224, 167, 0.16)";
      context.beginPath();
      context.arc(width * 0.55, height + 160, width * 0.52, Math.PI * 1.1, Math.PI * 1.82);
      context.stroke();
      frame += 1;
      window.requestAnimationFrame(draw);
    }
    resize();
    window.addEventListener("resize", resize);
    draw();
  }
})();
