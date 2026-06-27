import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const appJs = readFileSync(join(root, "frontend", "app.js"), "utf8");
const serverPy = readFileSync(join(root, "backend", "server.py"), "utf8");

const modelGatewayIndex = appJs.indexOf("模型网关鉴权失败");
const quotaIndex = appJs.indexOf("模型网关额度不足");
const localTokenIndex = appJs.indexOf("Local Auth Token");

assert.ok(modelGatewayIndex >= 0, "frontend should explain upstream model gateway auth failures");
assert.ok(quotaIndex >= 0, "frontend should explain upstream model gateway quota failures");
assert.ok(localTokenIndex >= 0, "frontend should keep the Local Auth Token guidance for real backend auth failures");
assert.ok(
  quotaIndex < modelGatewayIndex,
  "quota failures should be matched before generic model gateway auth/env guidance"
);
assert.ok(
  modelGatewayIndex < localTokenIndex,
  "upstream model gateway auth failures should be matched before generic Local Auth Token guidance"
);

assert.match(
  serverPy,
  /模型网关鉴权失败/,
  "backend should return a specific message when the OpenAI-compatible gateway rejects credentials"
);
assert.match(
  serverPy,
  /模型网关额度不足/,
  "backend should return a specific message when the OpenAI-compatible gateway has insufficient quota"
);
