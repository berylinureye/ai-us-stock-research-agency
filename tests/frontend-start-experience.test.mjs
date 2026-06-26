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
  /class="run-progress"[\s\S]*预计 12:00[\s\S]*id="progressFill"/,
  "running view should include the 12-minute estimate progress bar"
);
assert.match(
  html,
  /class="workflow-output"[\s\S]*Agent 思考轨迹[\s\S]*id="workflowOutputList"/,
  "running conversation panel should include an agent thinking trace area"
);
assert.match(
  js,
  /ESTIMATED_RUN_MS\s*=\s*12\s*\*\s*60\s*\*\s*1000/,
  "running progress should use a 12-minute timer estimate"
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
