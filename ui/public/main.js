const state = { sessions: [], current: null, sortDir: "asc", hideHidden: false, mdPreview: false };
const turnMdCache = new Map();

const IMG_EXTS = new Set(["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"]);
function isImage(name) {
  const i = name.lastIndexOf(".");
  if (i < 0) return false;
  return IMG_EXTS.has(name.slice(i + 1).toLowerCase());
}
function rawUrl(name) {
  return "/raw/" + encodeURIComponent(name);
}
function turnMdUrl(turnId) {
  return "/turns_md/" + encodeURIComponent(turnId) + ".md";
}

const $ = (sel) => document.querySelector(sel);
const sessionsListEl = $("#sessions-list");
const searchEl = $("#search");
const turnsEmptyEl = $("#turns-empty");
const turnsContentEl = $("#turns-content");
const sessionTitleEl = $("#session-title");
const sessionMetaEl = $("#session-meta");
const turnsListEl = $("#turns-list");
const statusEl = $("#status");
const lockOverlayEl = $("#lock-overlay");

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || res.statusText);
  }
  return res.json();
}

async function fetchTurnMd(turnId) {
  if (turnMdCache.has(turnId)) return turnMdCache.get(turnId);
  const res = await fetch(turnMdUrl(turnId));
  const text = res.ok ? await res.text() : "";
  turnMdCache.set(turnId, text);
  return text;
}

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.style.color = isError ? "#a33" : "#666";
}

function formatRange(start, end) {
  if (start === end) return start;
  return `${start} → ${end}`;
}

function renderSessionsList() {
  const q = searchEl.value.trim().toLowerCase();
  sessionsListEl.innerHTML = "";
  const ordered = state.sortDir === "desc"
    ? [...state.sessions].sort((a, b) => b.start_time.localeCompare(a.start_time))
    : [...state.sessions].sort((a, b) => a.start_time.localeCompare(b.start_time));
  for (const s of ordered) {
    if (q && !s.title.toLowerCase().includes(q)) continue;
    if (state.hideHidden && s.visible_count === 0) continue;
    const li = document.createElement("li");
    li.dataset.id = s.session_id;
    if (state.current && state.current.session_id === s.session_id) li.classList.add("active");
    li.innerHTML = `
      <div class="session-title"></div>
      <div class="session-meta"></div>
    `;
    li.querySelector(".session-title").textContent = s.title || "(untitled)";
    li.querySelector(".session-meta").textContent =
      `${s.start_time.split(" ")[0]} · ${s.visible_count}/${s.turn_count} visible`;
    li.addEventListener("click", () => loadSession(s.session_id));
    sessionsListEl.appendChild(li);
  }
}

async function loadSessions() {
  setStatus("loading sessions…");
  const data = await api("/api/sessions");
  state.sessions = data.sessions;
  renderSessionsList();
  setStatus(`${state.sessions.length} sessions`);
}

async function loadSession(id) {
  setStatus("loading session…");
  const data = await api(`/api/sessions/${id}`);
  state.current = data.session;
  await renderTurns();
  renderSessionsList();
  setStatus(`session ${id}`);
}

async function renderTurns() {
  if (!state.current) {
    turnsEmptyEl.hidden = false;
    turnsContentEl.hidden = true;
    return;
  }
  turnsEmptyEl.hidden = true;
  turnsContentEl.hidden = false;
  sessionTitleEl.textContent = state.current.title || "(untitled)";
  sessionMetaEl.textContent =
    `${state.current.session_id} · ${formatRange(state.current.start_time, state.current.last_active_time)} · ${state.current.turns.length} turns`;
  turnsListEl.innerHTML = "";
  const visibleTurns = state.current.turns.filter((t) => !(state.hideHidden && !t.visibility_flag));
  const mdTexts = await Promise.all(visibleTurns.map((t) => fetchTurnMd(t.turn_id)));
  visibleTurns.forEach((turn, i) => {
    turnsListEl.appendChild(renderTurn(turn, mdTexts[i]));
  });
}

function renderTurn(turn, turnMdText) {
  const div = document.createElement("div");
  div.className = "turn" + (turn.visibility_flag ? "" : " hidden");
  const promptText = turn.prompt || "(no prompt — " + turn.kind + ")";
  div.innerHTML = `
    <div class="turn-head">
      <button class="toggle-btn"></button>
      <span class="turn-ts"></span>
      <span class="turn-kind"></span>
    </div>
    <div class="turn-prompt"></div>
    <div class="turn-response"></div>
    <div class="turn-attachments"></div>
  `;
  div.querySelector(".turn-ts").textContent = turn.timestamp;
  const kindEl = div.querySelector(".turn-kind");
  kindEl.textContent = turn.kind;
  kindEl.classList.add(turn.kind);
  const btn = div.querySelector(".toggle-btn");
  btn.dataset.visible = String(turn.visibility_flag);
  btn.textContent = turn.visibility_flag ? "Visible" : "Hidden";
  btn.addEventListener("click", () => toggleTurn(turn.turn_id, !turn.visibility_flag));
  div.querySelector(".turn-prompt").textContent = promptText;
  const respEl = div.querySelector(".turn-response");
  if (state.mdPreview && turnMdText && typeof marked !== "undefined") {
    respEl.classList.add("preview");
    respEl.innerHTML = marked.parse(turnMdText);
    if (typeof renderMathInElement === "function") {
      renderMathInElement(respEl, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "$", right: "$", display: false },
          { left: "\\[", right: "\\]", display: true },
          { left: "\\(", right: "\\)", display: false },
        ],
        throwOnError: false,
      });
    }
  } else {
    respEl.classList.remove("preview");
    respEl.textContent = turnMdText || "(no rendered MD)";
  }
  if (turn.attachments && turn.attachments.length) {
    const at = div.querySelector(".turn-attachments");
    if (state.mdPreview) {
      at.classList.add("preview");
      at.innerHTML = "";
      for (const name of turn.attachments) {
        if (isImage(name)) {
          const img = document.createElement("img");
          img.src = rawUrl(name);
          img.alt = name;
          img.title = name;
          img.loading = "lazy";
          at.appendChild(img);
        } else {
          const a = document.createElement("a");
          a.href = rawUrl(name);
          a.textContent = "📎 " + name;
          a.target = "_blank";
          a.rel = "noopener";
          at.appendChild(a);
        }
      }
    } else {
      at.classList.remove("preview");
      at.textContent = "📎 " + turn.attachments.join(", ");
    }
  }
  return div;
}

async function toggleTurn(turnId, visible) {
  if (!state.current) return;
  const sid = state.current.session_id;
  try {
    setStatus("toggling…");
    await api(`/api/sessions/${sid}/turns/${turnId}/visibility`, {
      method: "POST",
      body: JSON.stringify({ visible }),
    });
    const turn = state.current.turns.find((t) => t.turn_id === turnId);
    if (turn) turn.visibility_flag = visible;
    const summary = state.sessions.find((s) => s.session_id === sid);
    if (summary) {
      summary.visible_count = state.current.turns.filter((t) => t.visibility_flag).length;
    }
    await renderTurns();
    renderSessionsList();
    setStatus("saved");
  } catch (e) {
    setStatus(e.message, true);
  }
}

async function organizeAll() {
  if (!confirm("Export all sessions to exports/?")) return;
  lockOverlayEl.hidden = false;
  try {
    const data = await api("/api/export", { method: "POST", body: JSON.stringify({}) });
    setStatus(`exported ${data.files.length} files`);
  } catch (e) {
    setStatus(e.message, true);
  } finally {
    lockOverlayEl.hidden = true;
  }
}

async function reload() {
  setStatus("reloading…");
  turnMdCache.clear();
  await api("/api/reload", { method: "POST", body: JSON.stringify({}) });
  await loadSessions();
}

searchEl.addEventListener("input", renderSessionsList);
$("#organize-btn").addEventListener("click", organizeAll);
$("#reload-btn").addEventListener("click", reload);
$("#sort-btn").addEventListener("click", () => {
  state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
  $("#sort-btn").textContent = state.sortDir === "asc" ? "Time ↑" : "Time ↓";
  renderSessionsList();
});
$("#hide-hidden").addEventListener("change", (e) => {
  state.hideHidden = e.target.checked;
  renderSessionsList();
  renderTurns();
});
$("#md-preview").addEventListener("change", (e) => {
  state.mdPreview = e.target.checked;
  renderTurns();
});

loadSessions().catch((e) => setStatus(e.message, true));
