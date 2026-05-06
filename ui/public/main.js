const state = {
  sessions: [],
  topics: [],
  selected: new Set(),
  current: null,        // current session detail
  currentTopic: null,   // current topic detail
  view: "empty",        // empty | turns | topic
  sortDir: "desc",
  topicSortDir: "desc",
  expandedTopics: new Set(),
  hideHidden: true,
  hideMissing: true,
  mdPreview: true,
};
const turnMdCache = new Map();

const IMG_EXTS = new Set(["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"]);
const isImage = (n) => { const i = n.lastIndexOf("."); return i >= 0 && IMG_EXTS.has(n.slice(i + 1).toLowerCase()); };
const rawUrl = (n) => "/raw/" + encodeURIComponent(n);
const turnMdUrl = (id) => "/turns_md/" + encodeURIComponent(id) + ".md";

function displayTitle(s) {
  return s.title || "(untitled)";
}
const displayPrompt = (t) => (t.prompt2 || t.prompt || "");

const ABS_URL_RE = /^(https?:|\/|#|mailto:|tel:|data:)/i;
function rewriteAttachmentUrls(root) {
  // Marked renders attachment-list links from per-turn MD as relative hrefs
  // like `image-...png`. Rewrite them to `/raw/<name>` so they hit the static
  // mount; do the same for any inline relative <img src>. Cached MD stays
  // portable (no /raw/ prefix on disk) so exports remain self-contained.
  root.querySelectorAll("a[href]").forEach((a) => {
    const h = a.getAttribute("href");
    if (h && !ABS_URL_RE.test(h)) {
      a.href = "/raw/" + encodeURIComponent(h);
      a.target = "_blank";
      a.rel = "noopener";
    }
  });
  root.querySelectorAll("img[src]").forEach((img) => {
    const s = img.getAttribute("src");
    if (s && !ABS_URL_RE.test(s)) img.src = "/raw/" + encodeURIComponent(s);
  });
}

const $ = (sel) => document.querySelector(sel);
const elTopicsBody = $("#topics-body");
const elTopicsCount = $("#topics-count");
const elUncatList = $("#uncat-list");
const elUncatCount = $("#uncat-count");
const elSearch = $("#search");
const elTurnsEmpty = $("#turns-empty");
const elTurnsContent = $("#turns-content");
const elTopicContent = $("#topic-content");
const elSessionTitle = $("#session-title");
const elSessionMeta = $("#session-meta");
const elTurnsList = $("#turns-list");
const elStatus = $("#status");
const elLockOverlay = $("#lock-overlay");
const elMSBar = $("#multi-select-bar");
const elMSCount = $("#ms-count");
const elMSAdd = $("#ms-add");
const elMSRemove = $("#ms-remove");

// ---------- helpers ----------

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || res.statusText);
  }
  return res.json();
}

function setStatus(msg, isError = false) {
  elStatus.textContent = msg;
  elStatus.style.color = isError ? "#a33" : "#666";
}

function show(view) {
  state.view = view;
  elTurnsEmpty.hidden = view !== "empty";
  elTurnsContent.hidden = view !== "turns";
  elTopicContent.hidden = view !== "topic";
}

function topicById(id) { return state.topics.find((t) => t.topicId === id); }
function sessionSummary(id) { return state.sessions.find((s) => s.sessionId === id); }

// ---------- data loading ----------

function metricsString() {
  const hiddenSessions = state.sessions.filter((s) => s.visibleCount === 0).length;
  let totalTurns = 0, hiddenTurns = 0, missingTurns = 0;
  for (const ss of state.sessions) {
    totalTurns += ss.turnCount;
    hiddenTurns += ss.turnCount - ss.visibleCount;
    missingTurns += ss.missingCount || 0;
  }
  return (
    `${state.topics.length} topics\n` +
    `${state.sessions.length} sessions (${hiddenSessions} hidden)\n` +
    `${totalTurns} turns (${hiddenTurns} hidden, ${missingTurns} missing)`
  );
}

async function loadAll() {
  setStatus("loading…");
  const [s, t] = await Promise.all([api("/api/sessions"), api("/api/topics")]);
  state.sessions = s.sessions;
  state.topics = t.topics;
  renderSidebar();
  setStatus("");
}

async function fetchTurnMd(turnId) {
  if (turnMdCache.has(turnId)) return turnMdCache.get(turnId);
  const res = await fetch(turnMdUrl(turnId));
  const text = res.ok ? await res.text() : "";
  turnMdCache.set(turnId, text);
  return text;
}

// ---------- sidebar ----------

function renderSidebar() {
  const q = elSearch.value.trim().toLowerCase();
  const matchesQ = (s) => !q || s.title.toLowerCase().includes(q);
  const isVisible = (s) => !state.hideHidden || s.visibleCount > 0;
  const ord = state.sortDir === "desc"
    ? (a, b) => b.beginTime.localeCompare(a.beginTime)
    : (a, b) => a.beginTime.localeCompare(b.beginTime);

  // Topics group
  elTopicsBody.innerHTML = "";
  const topicTime = (tp) => tp.endTime || tp.created;
  const topicOrd = state.topicSortDir === "desc"
    ? (a, b) => topicTime(b).localeCompare(topicTime(a))
    : (a, b) => topicTime(a).localeCompare(topicTime(b));
  for (const tp of [...state.topics].sort(topicOrd)) {
    const tDiv = document.createElement("div");
    tDiv.className = "topic-row";
    tDiv.dataset.id = tp.topicId;
    if (state.currentTopic && state.currentTopic.topicId === tp.topicId) tDiv.classList.add("active");
    const head = document.createElement("div");
    head.className = "topic-head-row";
    head.innerHTML = `<div class="topic-text"><div class="topic-name"></div><div class="topic-time"></div></div><span class="topic-count"></span>`;
    head.querySelector(".topic-name").textContent = tp.name;
    head.querySelector(".topic-time").textContent = tp.endTime ? tp.endTime.split(" ")[0] : "";
    head.querySelector(".topic-count").textContent = tp.sessionCount;
    head.addEventListener("click", () => {
      if (state.expandedTopics.has(tp.topicId)) state.expandedTopics.delete(tp.topicId);
      else state.expandedTopics.add(tp.topicId);
      loadTopic(tp.topicId);
    });
    tDiv.appendChild(head);

    if (state.expandedTopics.has(tp.topicId)) {
      const ul = document.createElement("ul");
      ul.className = "group-list nested";
      const memberSummaries = state.sessions
        .filter((s) => s.topicId === tp.topicId && matchesQ(s) && isVisible(s))
        .sort((a, b) => a.beginTime.localeCompare(b.beginTime));
      for (const s of memberSummaries) ul.appendChild(sessionRow(s, tp.topicId));
      tDiv.appendChild(ul);
    }
    elTopicsBody.appendChild(tDiv);
  }
  elTopicsCount.textContent = state.topics.length;

  // Uncategorized group
  elUncatList.innerHTML = "";
  const uncat = state.sessions
    .filter((s) => !s.topicId && matchesQ(s) && isVisible(s))
    .sort(ord);
  for (const s of uncat) elUncatList.appendChild(sessionRow(s, null));
  elUncatCount.textContent = uncat.length;

  // Refresh add-to dropdown
  refreshAddToDropdown();
  refreshMultiSelectBar();
  refreshExpandLabel();
}

function sessionRow(s, parentTopicId) {
  const li = document.createElement("li");
  li.className = "session-row";
  li.dataset.id = s.sessionId;
  if (state.current && state.current.sessionId === s.sessionId) li.classList.add("active");
  li.innerHTML = `
    <input type="checkbox" class="session-check" />
    <div class="session-text">
      <div class="session-title"></div>
      <div class="session-meta"></div>
    </div>
  `;
  const cb = li.querySelector(".session-check");
  cb.checked = state.selected.has(s.sessionId);
  cb.addEventListener("click", (e) => e.stopPropagation());
  cb.addEventListener("change", () => {
    if (cb.checked) state.selected.add(s.sessionId);
    else state.selected.delete(s.sessionId);
    refreshMultiSelectBar();
  });
  li.querySelector(".session-title").textContent = displayTitle(s);
  li.querySelector(".session-meta").textContent =
    `${s.beginTime.split(" ")[0]} · ${s.visibleCount}/${s.turnCount} visible`;
  li.addEventListener("click", () => loadSession(s.sessionId));
  return li;
}

function refreshMultiSelectBar() {
  const n = state.selected.size;
  elMSBar.hidden = n === 0;
  elMSCount.textContent = `${n} selected`;
  // Show "− Topic" only when ALL selected belong to the SAME topic
  const ids = [...state.selected];
  const topicIds = new Set(ids.map((sid) => sessionSummary(sid)?.topicId || null));
  const allInSame = ids.length > 0 && topicIds.size === 1 && !topicIds.has(null);
  elMSRemove.hidden = !allInSame;
}

function refreshAddToDropdown() {
  elMSAdd.innerHTML = '<option value="">Add to…</option>';
  for (const t of state.topics) {
    const opt = document.createElement("option");
    opt.value = t.topicId;
    opt.textContent = `${t.name} (${t.sessionCount})`;
    elMSAdd.appendChild(opt);
  }
}

// ---------- session view ----------

async function loadSession(id) {
  const data = await api(`/api/sessions/${id}`);
  state.current = data.session;
  state.currentTopic = null;
  show("turns");
  renderSessionView();
  renderSidebar();
}

async function renderSessionView() {
  if (!state.current) return;
  elSessionTitle.textContent = displayTitle(state.current);
  const range = state.current.beginTime === state.current.endTime
    ? state.current.beginTime
    : `${state.current.beginTime} → ${state.current.endTime}`;
  elSessionMeta.textContent =
    `${state.current.sessionId} · ${range} · ${state.current.turns.length} turns`;
  elTurnsList.innerHTML = "";
  const visibleTurns = state.current.turns.filter((t) =>
    !(state.hideHidden && !t.visibilityFlag) && !(state.hideMissing && t.missing)
  );
  const mdTexts = await Promise.all(visibleTurns.map((t) => fetchTurnMd(t.turnId)));
  visibleTurns.forEach((t, i) => elTurnsList.appendChild(renderTurn(t, mdTexts[i])));
}

function renderTurn(turn, turnMdText) {
  const div = document.createElement("div");
  div.className = "turn" + (turn.visibilityFlag ? "" : " hidden");
  const shown = displayPrompt(turn);
  const promptText = shown || "(no prompt — " + turn.kind + ")";
  div.innerHTML = `
    <div class="turn-head">
      <button class="toggle-btn"></button>
      <span class="turn-ts"></span>
      <span class="turn-kind"></span>
      <button class="icon-btn turn-edit" title="Edit prompt (prompt2)">✎</button>
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
  btn.dataset.visible = String(turn.visibilityFlag);
  btn.textContent = turn.visibilityFlag ? "Visible" : "Hidden";
  btn.addEventListener("click", () => toggleTurn(turn.turnId, !turn.visibilityFlag));
  const editBtn = div.querySelector(".turn-edit");
  if (turn.prompt2) editBtn.classList.add("edited");
  editBtn.addEventListener("click", () => editTurnPrompt(turn.turnId));
  const promptEl = div.querySelector(".turn-prompt");
  promptEl.textContent = promptText;
  if (turn.prompt2) promptEl.classList.add("edited");
  const respEl = div.querySelector(".turn-response");
  if (state.mdPreview && turnMdText && typeof marked !== "undefined") {
    respEl.classList.add("preview");
    respEl.innerHTML = marked.parse(turnMdText);
    rewriteAttachmentUrls(respEl);
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
          img.src = rawUrl(name); img.alt = name; img.title = name; img.loading = "lazy";
          at.appendChild(img);
        } else {
          const a = document.createElement("a");
          a.href = rawUrl(name); a.textContent = "📎 " + name;
          a.target = "_blank"; a.rel = "noopener";
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

async function editTurnPrompt(turnId) {
  if (!state.current) return;
  const turn = state.current.turns.find((tt) => tt.turnId === turnId);
  if (!turn) return;
  const current = turn.prompt2 || turn.prompt || "";
  const next = prompt(`Edit displayed prompt (clear to revert to original).\nOriginal:\n${turn.prompt || "(empty)"}`, current);
  if (next === null) return;
  const prompt2 = next.trim();
  if (prompt2 === current) return;
  try {
    setStatus("saving…");
    const data = await api(`/api/sessions/${state.current.sessionId}/turns/${turnId}/prompt2`, {
      method: "PATCH", body: JSON.stringify({ prompt2 }),
    });
    turn.prompt2 = prompt2;
    turnMdCache.delete(turnId);
    if (data.summary) {
      const i = state.sessions.findIndex((x) => x.sessionId === data.summary.sessionId);
      if (i >= 0) state.sessions[i] = data.summary;
    }
    await renderSessionView();
    renderSidebar();
    setStatus("saved");
  } catch (e) { setStatus(e.message, true); }
}

async function toggleTurn(turnId, visible) {
  if (!state.current) return;
  const sid = state.current.sessionId;
  try {
    setStatus("toggling…");
    const data = await api(`/api/sessions/${sid}/turns/${turnId}/visibility`, {
      method: "POST", body: JSON.stringify({ visible }),
    });
    const t = state.current.turns.find((tt) => tt.turnId === turnId);
    if (t) t.visibilityFlag = visible;
    if (data.summary) {
      const i = state.sessions.findIndex((x) => x.sessionId === data.summary.sessionId);
      if (i >= 0) state.sessions[i] = data.summary;
    }
    await renderSessionView();
    renderSidebar();
    setStatus("saved");
  } catch (e) { setStatus(e.message, true); }
}

// ---------- topic view ----------

async function loadTopic(topicId) {
  const data = await api(`/api/topics/${topicId}`);
  state.currentTopic = data.topic;
  state.currentTopicMembers = data.sessions || [];
  state.current = null;
  show("topic");
  renderTopicView();
  renderSidebar();
}

function renderTopicView() {
  const t = state.currentTopic;
  if (!t) return;
  $("#topic-title").textContent = t.name;
  $("#topic-meta").textContent = `${t.topicId} · created ${t.created} · ${t.sessionIds.length} sessions`;
  $("#topic-description").value = t.description || "";

  const ol = $("#topic-sessions");
  ol.innerHTML = "";
  state.currentTopicMembers.forEach((s, idx) => {
    const li = document.createElement("li");
    li.className = "topic-session-row";
    li.innerHTML = `
      <div class="reorder">
        <button class="up" title="Move up" ${idx === 0 ? "disabled" : ""}>↑</button>
        <button class="down" title="Move down" ${idx === state.currentTopicMembers.length - 1 ? "disabled" : ""}>↓</button>
      </div>
      <div class="ts-text">
        <div class="ts-title"></div>
        <div class="ts-meta"></div>
      </div>
      <button class="ts-open">Open</button>
      <button class="ts-remove" title="Remove from this Topic">×</button>
    `;
    li.querySelector(".ts-title").textContent = displayTitle(s);
    li.querySelector(".ts-meta").textContent = `${s.sessionId} · ${s.visibleCount}/${s.turnCount} visible`;
    li.querySelector(".up").addEventListener("click", () => reorder(idx, idx - 1));
    li.querySelector(".down").addEventListener("click", () => reorder(idx, idx + 1));
    li.querySelector(".ts-open").addEventListener("click", () => loadSession(s.sessionId));
    li.querySelector(".ts-remove").addEventListener("click", () => removeOneFromTopic(s.sessionId));
    ol.appendChild(li);
  });
}

async function reorder(fromIdx, toIdx) {
  if (toIdx < 0 || toIdx >= state.currentTopicMembers.length) return;
  const ids = state.currentTopic.sessionIds.slice();
  const [moved] = ids.splice(fromIdx, 1);
  ids.splice(toIdx, 0, moved);
  try {
    setStatus("reordering…");
    const data = await api(`/api/topics/${state.currentTopic.topicId}/order`, {
      method: "PUT", body: JSON.stringify({ sessionIds: ids }),
    });
    state.currentTopic = data.topic;
    // Reorder local member array to match
    const order = new Map(ids.map((sid, i) => [sid, i]));
    state.currentTopicMembers.sort((a, b) => order.get(a.sessionId) - order.get(b.sessionId));
    renderTopicView();
    setStatus("saved");
  } catch (e) { setStatus(e.message, true); }
}

async function removeOneFromTopic(sessionId) {
  try {
    setStatus("removing from topic…");
    const data = await api(`/api/topics/${state.currentTopic.topicId}/sessions`, {
      method: "DELETE", body: JSON.stringify({ sessionIds: [sessionId] }),
    });
    state.currentTopic = data.topic;
    await loadAll();
    state.currentTopicMembers = state.currentTopicMembers.filter((s) => s.sessionId !== sessionId);
    renderTopicView();
    setStatus("removed");
  } catch (e) { setStatus(e.message, true); }
}

async function deleteCurrentTopic() {
  const t = state.currentTopic;
  if (!t) return;
  if (!confirm(`Delete topic "${t.name}"? Sessions return to Uncategorized; nothing else is deleted.`)) return;
  try {
    setStatus("deleting topic…");
    await api(`/api/topics/${t.topicId}`, { method: "DELETE" });
    state.currentTopic = null;
    state.currentTopicMembers = [];
    show("empty");
    await loadAll();
    setStatus("topic deleted");
  } catch (e) { setStatus(e.message, true); }
}

async function organizeCurrentTopic() {
  const t = state.currentTopic;
  if (!t) return;
  if (!confirm(`Export topic "${t.name}" to data/4-exports/?`)) return;
  elLockOverlay.hidden = false;
  try {
    const data = await api("/api/export", { method: "POST", body: JSON.stringify({ topicIds: [t.topicId] }) });
    setStatus(`exported ${data.files.length} file(s)`);
  } catch (e) { setStatus(e.message, true); }
  finally { elLockOverlay.hidden = true; }
}

async function saveTopicDescription() {
  const t = state.currentTopic;
  if (!t) return;
  const desc = $("#topic-description").value;
  if (desc === (t.description || "")) return;
  try {
    const data = await api(`/api/topics/${t.topicId}`, {
      method: "PATCH", body: JSON.stringify({ description: desc }),
    });
    state.currentTopic = data.topic;
    setStatus("description saved");
  } catch (e) { setStatus(e.message, true); }
}

async function renameCurrentTopic() {
  const t = state.currentTopic;
  if (!t) return;
  const name = prompt("Rename topic:", t.name);
  if (!name || !name.trim() || name === t.name) return;
  try {
    const data = await api(`/api/topics/${t.topicId}`, {
      method: "PATCH", body: JSON.stringify({ name: name.trim() }),
    });
    state.currentTopic = data.topic;
    renderTopicView();
    await loadAll();
    setStatus("renamed");
  } catch (e) { setStatus(e.message, true); }
}

// ---------- multi-select actions ----------

function clearSelection() {
  state.selected.clear();
  renderSidebar();
}

async function createTopicFromSelection() {
  const sids = [...state.selected];
  if (sids.length === 0) return;
  const name = prompt(`Create new Topic from ${sids.length} selected session(s).\nName:`);
  if (!name || !name.trim()) return;
  try {
    const data = await api("/api/topics", {
      method: "POST", body: JSON.stringify({ name: name.trim(), sessionIds: sids }),
    });
    state.selected.clear();
    await loadAll();
    await loadTopic(data.topic.topicId);
    setStatus(`created topic "${data.topic.name}"`);
  } catch (e) { setStatus(e.message, true); }
}

async function addSelectionToTopic(topicId) {
  if (!topicId) return;
  const sids = [...state.selected];
  if (sids.length === 0) return;
  try {
    await api(`/api/topics/${topicId}/sessions`, {
      method: "POST", body: JSON.stringify({ sessionIds: sids }),
    });
    state.selected.clear();
    await loadAll();
    setStatus(`added ${sids.length} to topic`);
  } catch (e) { setStatus(e.message, true); }
  finally { elMSAdd.value = ""; }
}

async function removeSelectionFromTopic() {
  const sids = [...state.selected];
  if (sids.length === 0) return;
  const topicId = sessionSummary(sids[0])?.topicId;
  if (!topicId) return;
  try {
    await api(`/api/topics/${topicId}/sessions`, {
      method: "DELETE", body: JSON.stringify({ sessionIds: sids }),
    });
    state.selected.clear();
    await loadAll();
    setStatus(`released ${sids.length} session(s)`);
  } catch (e) { setStatus(e.message, true); }
}

// ---------- top-bar actions ----------

async function organizeAll() {
  if (!confirm("Export all sessions to data/4-exports/?")) return;
  elLockOverlay.hidden = false;
  try {
    const data = await api("/api/export", { method: "POST", body: JSON.stringify({}) });
    setStatus(`exported ${data.files.length} files`);
  } catch (e) { setStatus(e.message, true); }
  finally { elLockOverlay.hidden = true; }
}

async function reload() {
  setStatus("reloading…");
  turnMdCache.clear();
  await api("/api/reload", { method: "POST", body: JSON.stringify({}) });
  await loadAll();
}

// ---------- wiring ----------

elSearch.addEventListener("input", renderSidebar);
$("#metrics-btn").addEventListener("click", () => alert(metricsString()));
$("#organize-btn").addEventListener("click", organizeAll);
$("#reload-btn").addEventListener("click", reload);
$("#sort-btn").addEventListener("click", () => {
  state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
  $("#sort-btn").textContent = state.sortDir === "asc" ? "Time ↑" : "Time ↓";
  renderSidebar();
});
$("#topics-sort-btn").addEventListener("click", () => {
  state.topicSortDir = state.topicSortDir === "asc" ? "desc" : "asc";
  $("#topics-sort-btn").textContent = state.topicSortDir === "asc" ? "Time ↑" : "Time ↓";
  renderSidebar();
});
function refreshExpandLabel() {
  const ids = state.topics.map((t) => t.topicId);
  const all = ids.length > 0 && ids.every((id) => state.expandedTopics.has(id));
  $("#topics-expand-btn").textContent = all ? "Collapse" : "Expand";
}
$("#topics-expand-btn").addEventListener("click", () => {
  const ids = state.topics.map((t) => t.topicId);
  const all = ids.length > 0 && ids.every((id) => state.expandedTopics.has(id));
  if (all) state.expandedTopics.clear();
  else state.expandedTopics = new Set(ids);
  refreshExpandLabel();
  renderSidebar();
});
$("#hide-hidden").addEventListener("change", (e) => {
  state.hideHidden = e.target.checked;
  renderSidebar();
  if (state.view === "turns") renderSessionView();
});
$("#hide-missing").addEventListener("change", (e) => {
  state.hideMissing = e.target.checked;
  if (state.view === "turns") renderSessionView();
});
$("#md-preview").addEventListener("change", (e) => {
  state.mdPreview = e.target.checked;
  if (state.view === "turns") renderSessionView();
});

$("#ms-create").addEventListener("click", createTopicFromSelection);
$("#ms-add").addEventListener("change", (e) => addSelectionToTopic(e.target.value));
$("#ms-remove").addEventListener("click", removeSelectionFromTopic);
$("#ms-clear").addEventListener("click", clearSelection);

$("#topic-organize").addEventListener("click", organizeCurrentTopic);
$("#topic-delete").addEventListener("click", deleteCurrentTopic);
$("#topic-rename").addEventListener("click", renameCurrentTopic);
$("#topic-description").addEventListener("blur", saveTopicDescription);

loadAll().catch((e) => setStatus(e.message, true));
