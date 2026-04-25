const { spawn } = require("child_process");
const readline = require("readline");
const crypto = require("crypto");

class PythonBridge {
  constructor({ pythonPath, repoRoot, configPath }) {
    this.pythonPath = pythonPath;
    this.repoRoot = repoRoot;
    this.configPath = configPath;
    this.proc = null;
    this.pending = new Map();
    this.exportInFlight = false;
  }

  start() {
    if (this.proc) return;
    this.proc = spawn(
      this.pythonPath,
      ["-m", "engine.cli", "serve", "--config", this.configPath],
      { cwd: this.repoRoot, stdio: ["pipe", "pipe", "pipe"] }
    );
    const rl = readline.createInterface({ input: this.proc.stdout });
    rl.on("line", (line) => this._onLine(line));
    this.proc.stderr.on("data", (chunk) => {
      process.stderr.write(`[python] ${chunk}`);
    });
    this.proc.on("exit", (code) => {
      console.error(`[python] exited code=${code}`);
      this.proc = null;
      for (const { reject } of this.pending.values()) {
        reject(new Error(`python exited (code ${code})`));
      }
      this.pending.clear();
    });
  }

  stop() {
    if (!this.proc) return;
    try { this.send("shutdown", {}).catch(() => {}); } catch {}
    setTimeout(() => { if (this.proc) this.proc.kill(); }, 500);
  }

  send(cmd, args) {
    if (!this.proc) throw new Error("python bridge not started");
    if (cmd === "toggle_turn" && this.exportInFlight) {
      return Promise.reject(Object.assign(new Error("locked"), { code: "locked" }));
    }
    const id = crypto.randomBytes(6).toString("hex");
    const payload = JSON.stringify({ id, cmd, args: args || {} }) + "\n";
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, cmd });
      if (cmd === "export") this.exportInFlight = true;
      this.proc.stdin.write(payload);
    });
  }

  _onLine(line) {
    line = line.trim();
    if (!line) return;
    let msg;
    try { msg = JSON.parse(line); } catch (e) {
      console.error("[bridge] non-JSON line:", line);
      return;
    }
    const entry = this.pending.get(msg.id);
    if (!entry) return;
    this.pending.delete(msg.id);
    if (entry.cmd === "export") this.exportInFlight = false;
    if (msg.ok) entry.resolve(msg.data);
    else entry.reject(Object.assign(new Error(msg.error?.msg || "python error"), { detail: msg.error }));
  }
}

module.exports = { PythonBridge };
