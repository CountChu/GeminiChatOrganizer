const path = require("path");
const fs = require("fs");
const { spawnSync } = require("child_process");
const express = require("express");
const { PythonBridge } = require("./python_bridge");

const PORT = Number(process.env.PORT || 3030);
const REPO_ROOT = path.resolve(__dirname, "..");
const PYTHON_PATH = path.join(REPO_ROOT, ".venv", "bin", "python");
const CONFIG_PATH = path.join(REPO_ROOT, "sync_config.yaml");

function loadFlatYaml(p) {
  const out = {};
  for (const line of fs.readFileSync(p, "utf8").split("\n")) {
    const m = line.match(/^([a-z_]+):\s*(.*?)\s*$/);
    if (!m) continue;
    out[m[1]] = /^-?\d+$/.test(m[2]) ? parseInt(m[2], 10) : m[2];
  }
  return out;
}

const syncCfg = loadFlatYaml(CONFIG_PATH);
const RAW_DIR = path.resolve(REPO_ROOT, syncCfg.raw_dir);
const TURNS_MD_DIR = path.resolve(REPO_ROOT, syncCfg.turns_md_dir || "warehouse/turns_md");

console.log("Pre-rendering per-Turn MD cache...");
const render = spawnSync(PYTHON_PATH, ["-m", "engine.cli", "render", "--config", CONFIG_PATH], {
  cwd: REPO_ROOT,
  stdio: ["ignore", "inherit", "inherit"],
});
if (render.status !== 0) {
  console.error(`Renderer exited with code ${render.status}; aborting startup.`);
  process.exit(render.status || 1);
}

const bridge = new PythonBridge({ pythonPath: PYTHON_PATH, repoRoot: REPO_ROOT, configPath: CONFIG_PATH });
bridge.start();

const app = express();
app.use(express.json({ limit: "1mb" }));
app.use(express.static(path.join(__dirname, "public")));
app.use("/raw", express.static(RAW_DIR));
app.use("/turns_md", express.static(TURNS_MD_DIR));

function asHandler(fn) {
  return async (req, res) => {
    try {
      const out = await fn(req, res);
      res.json(out);
    } catch (e) {
      const status = e.code === "locked" ? 423 : 500;
      res.status(status).json({ error: e.message, detail: e.detail });
    }
  };
}

app.get("/api/sessions", asHandler(async () => bridge.send("list_sessions", {})));
app.get("/api/sessions/:id", asHandler(async (req) => bridge.send("get_session", { session_id: req.params.id })));
app.post("/api/sessions/:id/turns/:tid/visibility", asHandler(async (req) =>
  bridge.send("toggle_turn", { session_id: req.params.id, turn_id: req.params.tid, visible: !!req.body.visible })
));
app.post("/api/export", asHandler(async (req) => bridge.send("export", { session_ids: req.body?.session_ids || null })));
app.post("/api/reload", asHandler(async () => bridge.send("reload", {})));
app.get("/api/lock", (_req, res) => res.json({ locked: bridge.exportInFlight }));

const server = app.listen(PORT, () => {
  console.log(`Gemini Chat Organizer UI on http://localhost:${PORT}`);
});

function shutdown() {
  console.log("shutting down...");
  bridge.stop();
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 2000);
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
