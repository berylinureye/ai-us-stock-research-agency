import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const html = readFileSync(join(root, "frontend", "index.html"), "utf8");
const js = readFileSync(join(root, "frontend", "app.js"), "utf8");

const textareaMatch = html.match(/<textarea[\s\S]*?<\/textarea>/);
assert.ok(textareaMatch, "prompt textarea should exist");

const composerMatch = html.match(/<form class="composer"[\s\S]*?<\/form>/);
assert.ok(composerMatch, "research composer should exist");

const textareaMarkup = textareaMatch[0];
const composerMarkup = composerMatch[0];
const topbarMatch = html.match(/<header class="topbar"[\s\S]*?<\/header>/);
assert.ok(topbarMatch, "topbar should exist");

const topbarMarkup = topbarMatch[0];
assert.doesNotMatch(
  topbarMarkup,
  /class="brand"|美股周报研究台/,
  "initial topbar should not show the old product label"
);
assert.match(
  topbarMarkup,
  /<button class="back-button" id="backButton" type="button" hidden>返回<\/button>/,
  "back button should exist and be hidden on the initial input page"
);

assert.match(
  composerMarkup,
  /研究意图（可选，没想好可以直接开始）/,
  "research intent label should make the prompt optional"
);
assert.doesNotMatch(
  textareaMarkup,
  /AI\s*产业链|AI\s*行业/i,
  "prompt placeholder should not force users into AI-specific examples"
);

const sampleValues = [...html.matchAll(/data-sample="([^"]+)"/g)].map((match) => match[1]);
assert.ok(
  sampleValues.every((sample) => !/AI\s*产业链|AI\s*行业/i.test(sample)),
  "sample chips should be broad US-equity research prompts"
);

assert.match(
  js,
  /DEFAULT_RESEARCH_INTENT/,
  "empty prompt submissions should use a default research intent"
);
assert.match(
  html,
  /class="run-progress"[\s\S]*正在运行[\s\S]*id="progressFill"/,
  "running view should show live progress without a fixed 12-minute estimate"
);
assert.doesNotMatch(
  html,
  /预计 12:00/,
  "running view should not promise a fixed 12-minute duration"
);
assert.match(
  html,
  /id="progressPercent"[\s\S]*0%/,
  "running progress should show a visible percentage"
);
assert.match(
  js,
  /setRunProgress[\s\S]*progressPercent\.textContent\s*=\s*`\$\{Math\.round\(safePercent\)\}%`/,
  "progress updates should keep the visible percentage in sync with the bar"
);
assert.match(
  js,
  /aria-valuetext/,
  "progress updates should expose the percentage to assistive technology"
);
assert.match(
  html,
  /class="workflow-output"[\s\S]*Agent 思考轨迹[\s\S]*id="workflowOutputList"/,
  "running conversation panel should include an agent thinking trace area"
);
assert.match(
  html,
  /id="reportHistoryNavButton"[\s\S]*历史/,
  "top navigation should include a report history view"
);
assert.match(
  html,
  /id="reportHistorySection"[\s\S]*报告历史[\s\S]*id="reportHistoryList"[\s\S]*id="reportHistoryDetailBody"/,
  "the frontend should include a viewable report history section"
);
assert.match(
  html,
  /href="\.\/styles\.css\?v=\d{8}-[a-z0-9-]+"/,
  "stylesheet should be cache-busted so stale UI styles do not survive local reloads"
);
assert.match(
  html,
  /src="\.\/app\.js\?v=\d{8}-[a-z0-9-]+"/,
  "app script should be cache-busted so stale initialization code cannot survive local reloads"
);
assert.match(
  html,
  /class="pond-preview-visual"[\s\S]*assets\/pond-watch\.svg\?v=\d{8}-[a-z0-9-]+/,
  "pond preview should include a local visual asset instead of being a text-only strip"
);
assert.doesNotMatch(
  js,
  /ESTIMATED_RUN_MS|预计剩余|超过 12 分钟/,
  "running progress should avoid virtual fixed-duration countdown text"
);
assert.match(
  js,
  /thinkingTrace/,
  "streamed agent events should support structured thinking traces"
);
assert.match(
  js,
  /agent-trace-grid/,
  "workflow outputs should render public reasoning summaries instead of raw markdown first"
);
assert.match(
  js,
  /raw-section-disclosure/,
  "raw section markdown should be available only behind a disclosure"
);
assert.match(
  js,
  /function reportStatusFromPayload[\s\S]*researchActionPool[\s\S]*return "complete"/,
  "frontend status should treat reports with structured candidates as complete even when they mention data gaps"
);
{
  const statusFunction = js.match(/function reportStatusFromPayload\(payload\) \{[\s\S]*?\n  \}/)?.[0] || "";
  const topLevelFailureIndex = statusFunction.indexOf("研究未完成");
  const actionPoolIndex = statusFunction.indexOf("researchActionPool");
  const sectionFailureIndex = statusFunction.indexOf("section\\s*状态");
  assert.ok(topLevelFailureIndex >= 0, "frontend status should still detect top-level backend failure");
  assert.ok(actionPoolIndex >= 0, "frontend status should inspect structured candidates");
  assert.ok(sectionFailureIndex >= 0, "frontend status should still inspect failed section appendices");
  assert.ok(
    topLevelFailureIndex < actionPoolIndex && actionPoolIndex < sectionFailureIndex,
    "structured candidates should be checked after top-level failure but before appendix section-failed text"
  );
}
assert.match(
  js,
  /publicThinkingPreview\(trace\)/,
  "agent trace cards should summarize only the public 'what I am judging' sentence"
);
assert.doesNotMatch(
  js,
  /const preview = String\(output\.preview/,
  "agent trace card summaries should not expose raw event previews before expansion"
);
assert.match(
  js,
  /summary\.setAttribute\("role", "button"\)/,
  "agent trace summaries should expose button semantics"
);
assert.match(
  js,
  /const setOpen = \(open\) =>/,
  "agent trace cards should have explicit open/close handling"
);
assert.doesNotMatch(
  js,
  /if\s*\(\s*!prompt\s*\)\s*\{[\s\S]*?return;/,
  "empty prompt submissions should not be blocked"
);
assert.ok(
  !/state\.activeStep\s*\+\s*1/.test(js),
  "unknown stream stages should not automatically advance the workflow"
);
assert.match(
  js,
  /Workflow Error/,
  "run_error stream events should render as workflow errors instead of anonymous agent cards"
);
assert.match(
  js,
  /makeReportHistoryUrl\(["']\/api\/reports/,
  "frontend should call the backend report history API"
);
assert.match(
  js,
  /completeRun[\s\S]*loadReportHistory\(\{ quiet: true \}\)/,
  "successful or partial report completion should refresh the report history"
);
assert.match(
  js,
  /renderReportHistoryDetail/,
  "frontend should render a selected historical report"
);
assert.match(
  js,
  /if\s*\(\s*dataLine\s*===\s*"\[DONE\]"\s*\)\s*return\s+true/,
  "stream readers should treat [DONE] as a terminal event instead of waiting for keep-alive sockets"
);
assert.match(
  js,
  /reader\.cancel\(\)/,
  "stream readers should cancel the reader after [DONE] so completeRun can render the result page"
);
assert.match(
  js,
  /enterRunningState[\s\S]*els\.cancelButton\.hidden\s*=\s*false[\s\S]*els\.cancelButton\.disabled\s*=\s*false/,
  "the stop button should only be enabled while a workflow is running"
);
assert.match(
  js,
  /completeRun[\s\S]*els\.cancelButton\.hidden\s*=\s*true[\s\S]*els\.cancelButton\.disabled\s*=\s*true/,
  "the stop button should be hidden after the result page renders"
);
assert.match(
  js,
  /showRunError[\s\S]*els\.cancelButton\.hidden\s*=\s*true[\s\S]*els\.cancelButton\.disabled\s*=\s*true/,
  "the stop button should be hidden after a run error"
);
