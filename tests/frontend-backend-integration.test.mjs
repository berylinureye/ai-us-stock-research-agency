import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import net from "node:net";

const root = process.cwd();

function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => resolve(address.port));
    });
    server.on("error", reject);
  });
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForJson(url, { timeoutMs = 7000 } = {}) {
  const started = Date.now();
  let lastError;
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.json();
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await delay(150);
  }
  throw lastError || new Error(`Timed out waiting for ${url}`);
}

async function waitForText(url, { timeoutMs = 7000 } = {}) {
  const started = Date.now();
  let lastError;
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return response.text();
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await delay(150);
  }
  throw lastError || new Error(`Timed out waiting for ${url}`);
}

function startProcess(command, args, env = {}) {
  return spawn(command, args, {
    cwd: root,
    env: { ...process.env, ...env },
    stdio: ["ignore", "pipe", "pipe"]
  });
}

function stopProcess(child) {
  if (!child || child.killed) return;
  child.kill("SIGTERM");
}

const backendPort = await getFreePort();
const frontendPort = await getFreePort();
const reportHistoryDir = mkdtempSync(join(tmpdir(), "weekly-brief-history-"));

const backend = startProcess(
  "python3",
  ["backend/server.py", "--host", "127.0.0.1", "--port", String(backendPort)],
  {
    WEEKLY_BRIEF_MOCK: "1",
    REPORT_HISTORY_DIR: reportHistoryDir
  }
);
const frontend = startProcess("python3", [
  "-m",
  "http.server",
  String(frontendPort),
  "--bind",
  "127.0.0.1",
  "--directory",
  "frontend"
]);

try {
  const health = await waitForJson(`http://127.0.0.1:${backendPort}/api/health`);
  assert.equal(health.ok, true);
  assert.equal(health.mode, "mock");

  const html = await waitForText(`http://127.0.0.1:${frontendPort}/`);
  assert.match(html, /id="researchForm"/, "frontend static server should serve the research form");
  assert.match(html, /id="endpointInput"/, "frontend should expose configurable backend endpoint");

  const appJs = await waitForText(`http://127.0.0.1:${frontendPort}/app.js?v=20260627-streamdone`);
  assert.match(appJs, /DEFAULT_ENDPOINT/, "frontend app script should load");

  const response = await fetch(`http://127.0.0.1:${backendPort}/api/weekly-brief`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    },
    body: JSON.stringify({ prompt: "联调 smoke test" })
  });
  assert.equal(response.status, 200);
  const payload = await response.json();

  assert.match(payload.reportMarkdown, /^# 老板决策页/m);
  assert.match(payload.reportMarkdown, /Confidence \| Est\. Upside Range \| Est\. Holding Range \| Exit \/ Trim Rule/);
  assert.match(payload.evidenceMarkdown, /## Data Node Status/);
  assert.deepEqual(payload.researchActionPool, [], "No Rating smoke reports should not expose add-to-pond candidates");
  assert.ok(payload.runMetadata?.historyId, "weekly brief response should include persisted history id");

  const history = await waitForJson(`http://127.0.0.1:${backendPort}/api/reports`);
  assert.equal(history.summary.count, 1);
  assert.equal(history.items[0].id, payload.runMetadata.historyId);
} finally {
  stopProcess(frontend);
  stopProcess(backend);
  rmSync(reportHistoryDir, { recursive: true, force: true });
}
