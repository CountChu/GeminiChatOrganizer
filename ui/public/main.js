const state = {
  sessions: [],
  topics: [],
  selected: new Set(),
  current: null,        // current session detail
  currentTopic: null,   // current topic detail
  view: "empty",        // empty | turns | topic
  sortDir: "asc",
  hideHidden: false,
  mdPreview: false,
};
const turnMdCache = new Map();

const IMG_EXTS = new Set(["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"]);
const isImage = (n) => { const i = n.lastIndexOf("."); return i >= 0 && IMG_EXTS.has(n.slice(i + 1).toLowerCase()); };
const rawUrl = (n) => "/raw/" + encodeURIComponent(n);
const turnMdUrl = (id) => "/turns_md/" + encodeURIComponent(id) + ".md";

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

function topicById(id) { return state.topics.find((t) => t.topic_id === id); }
function sessionSummary(id) { return state.sessions.find((s) => s.session_id === id); }

// ---------- data loading ----------

async function loadAll() {
  setStatus("loading…");
  const [s, t] = await Promise.all([api("/api/sessions"), api("/api/topics")]);
  state.sessions = s.sessions;
  state.topics = t.topics;
  renderSidebar();
  setStatus(`${state.sessions.length} sessions · ${state.topics.length} topics`);
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
  const ord = state.sortDir === "desc"
    ? (a, b) => b.start_time.localeCompare(a.start_time)
    : (a, b) => a.start_time.localeCompare(b.start_time);

  // Topics group
  elTopicsBody.innerHTML = "";
  for (const tp of [...state.topics].sort((a, b) => a.created_at.localeCompare(b.created_at))) {
    const tDiv = document.createElement("div");
    tDiv.className = "topic-row";
    tDiv.dataset.id = tp.topic_id;
    if (state.currentTopic && state.currentTopic.topic_id === tp.topic_id) tDiv.classList.add("active");
    const head = document.createElement("div");
    head.className = "topic-head-row";
    head.innerHTML = `<span class="topic-name"></span><span class="topic-count"></span>`;
    head.querySelector(".topic-name").textContent = tp.name;
    head.querySelector(".topic-count").textContent = tp.session_count;
    head.addEventListener("click", () => loadTopic(tp.topic_id));
    tDiv.appendChild(head);

    const ul = document.createElement("ul");
    ul.className = "group-list nested";
    const memberSummaries = state.sessions
      .filter((s) => s.topic_id === tp.topic_id && matchesQ(s) && !(state.hideHidden && s.visible_count === 0))
      .sort(ord);
    for (const s of memberSummaries) ul.appendChild(sessionRow(s, tp.topic_id));
    tDiv.appendChild(ul);
    elTopicsBody.appendChild(tDiv);
  }
  elTopicsCount.textContent = state.topics.length;

  // Uncategorized group
  elUncatList.innerHTML = "";
  const uncat = state.sessions
    .filter((s) => !s.topic_id && matchesQ(s) && !(state.hideHidden && s.visible_count === 0))
    .sort(ord);
  for (const s of uncat) elUncatList.appendChild(sessionRow(s, null));
  elUncatCount.textContent = uncat.length;

  // Refresh add-to dropdown
  refreshAddToDropdown();
  refreshMultiSelectBar();
}

function sessionRow(s, parentTopicId) {
  const li = document.createElement("li");
  li.className = "session-row";
  li.dataset.id = s.session_id;
  if (state.current && state.current.session_id === s.session_id) li.classList.add("active");
  li.innerHTML = `
    <input type="checkbox" class="session-check" />
    <div class="session-text">
      <div class="session-title"></div>
      <div class="session-meta"></div>
    </div>
  `;
  const cb = li.querySelector(".session-check");
  cb.checked = state.selected.has(s.session_id);
  cb.addEventListener("click", (e) => e.stopPropagation());
  cb.addEventListener("change", () => {
    if (cb.checked) state.selected.add(s.session_id);
    else state.selected.delete(s.session_id);
    refreshMultiSelectBar();
  });
  li.querySelector(".session-title").textContent = s.title || "(untitled)";
  li.querySelector(".session-meta").textContent =
    `${s.start_time.split(" ")[0]} · ${s.visible_count}/${s.turn_count} visible`;
  li.addEventListener("click", () => loadSession(s.session_id));
  return li;
}

function refreshMultiSelectBar() {
  const n = state.selected.size;
  elMSBar.hidden = n === 0;
  elMSCount.textContent = `${n} selected`;
  // Show "− Topic" only when ALL selected belong to the SAME topic
  const ids = [...state.selected];
  const topicIds = new Set(ids.map((sid) => sessionSummary(sid)?.topic_id || null));
  const allInSame = ids.length > 0 && topicIds.size === 1 && !topicIds.has(null);
  elMSRemove.hidden = !allInSame;
}

function refreshAddToDropdown() {
  elMSAdd.innerHTML = '<option value="">Add to…</option>';
  for (const t of state.topics) {
    const opt = document.createElement("option");
    opt.value = t.topic_id;
    opt.textContent = `${t.name} (${t.session_count})`;
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
  elSessionTitle.textContent = state.current.title || "(untitled)";
  const range = state.current.start_time === state.current.last_active_time
    ? state.current.start_time
    : `${state.current.start_time} → ${state.current.last_active_time}`;
  elSessionMeta.textContent =
    `${state.current.session_id} · ${range} · ${state.current.turns.length} turns`;
  elTurnsList.innerHTML = "";
  const visibleTurns = state.current.turns.filter((t) => !(state.hideHidden && !t.visibility_flag));
  const mdTexts = await Promise.all(visibleTurns.map((t) => fetchTurnMd(t.turn_id)));
  visibleTurns.forEach((t, i) => elTurnsList.appendChild(renderTurn(t, mdTexts[i])));
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

async function toggleTurn(turnId, visible) {
  if (!state.current) return;
  const sid = state.current.session_id;
  try {
    setStatus("toggling…");
    await api(`/api/sessions/${sid}/turns/${turnId}/visibility`, {
      method: "POST", body: JSON.stringify({ visible }),
    });
    const t = state.current.turns.find((tt) => tt.turn_id === turnId);
    if (t) t.visibility_flag = visible;
    const summary = sessionSummary(sid);
    if (summary) summary.visible_count = state.current.turns.filter((tt) => tt.visibility_flag).length;
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
  $("#topic-meta").textContent = `${t.topic_id} · created ${t.created_at} · ${t.session_ids.length} sessions`;
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
    li.querySelector(".ts-title").textContent = s.title || "(untitled)";
    li.querySelector(".ts-meta").textContent = `${s.session_id} · ${s.visible_count}/${s.turn_count} visible`;
    li.querySelector(".up").addEventListener("click", () => reorder(idx, idx - 1));
    li.querySelector(".down").addEventListener("click", () => reorder(idx, idx + 1));
    li.querySelector(".ts-open").addEventListener("click", () => loadSession(s.session_id));
    li.querySelector(".ts-remove").addEventListener("click", () => removeOneFromTopic(s.session_id));
    ol.appendChild(li);
  });
}

async function reorder(fromIdx, toIdx) {
  if (toIdx < 0 || toIdx >= state.currentTopicMembers.length) return;
  const ids = state.currentTopic.session_ids.slice();
  const [moved] = ids.splice(fromIdx, 1);
  ids.splice(toIdx, 0, moved);
  try {
    setStatus("reordering…");
    const data = await api(`/api/topics/${state.currentTopic.topic_id}/order`, {
      method: "PUT", body: JSON.stringify({ session_ids: ids }),
    });
    state.currentTopic = data.topic;
    // Reorder local member array to match
    const order = new Map(ids.map((sid, i) => [sid, i]));
    state.currentTopicMembers.sort((a, b) => order.get(a.session_id) - order.get(b.session_id));
    renderTopicView();
    setStatus("saved");
  } catch (e) { setStatus(e.message, true); }
}

async function removeOneFromTopic(sessionId) {
  try {
    setStatus("removing from topic…");
    const data = await api(`/api/topics/${state.currentTopic.topic_id}/sessions`, {
      method: "DELETE", body: JSON.stringify({ session_ids: [sessionId] }),
    });
    state.currentTopic = data.topic;
    await loadAll();
    state.currentTopicMembers = state.currentTopicMembers.filter((s) => s.session_id !== sessionId);
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
    await api(`/api/topics/${t.topic_id}`, { method: "DELETE" });
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
  if (!confirm(`Export topic "${t.name}" to exports/?`)) return;
  elLockOverlay.hidden = false;
  try {
    const data = await api("/api/export", { method: "POST", body: JSON.stringify({ topic_ids: [t.topic_id] }) });
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
    const data = await api(`/api/topics/${t.topic_id}`, {
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
    const data = await api(`/api/topics/${t.topic_id}`, {
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
      method: "POST", body: JSON.stringify({ name: name.trim(), session_ids: sids }),
    });
    state.selected.clear();
    await loadAll();
    await loadTopic(data.topic.topic_id);
    setStatus(`created topic "${data.topic.name}"`);
  } catch (e) { setStatus(e.message, true); }
}

async function addSelectionToTopic(topicId) {
  if (!topicId) return;
  const sids = [...state.selected];
  if (sids.length === 0) return;
  try {
    await api(`/api/topics/${topicId}/sessions`, {
      method: "POST", body: JSON.stringify({ session_ids: sids }),
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
  const topicId = sessionSummary(sids[0])?.topic_id;
  if (!topicId) return;
  try {
    await api(`/api/topics/${topicId}/sessions`, {
      method: "DELETE", body: JSON.stringify({ session_ids: sids }),
    });
    state.selected.clear();
    await loadAll();
    setStatus(`released ${sids.length} session(s)`);
  } catch (e) { setStatus(e.message, true); }
}

// ---------- top-bar actions ----------

async function organizeAll() {
  if (!confirm("Export all sessions to exports/?")) return;
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
$("#organize-btn").addEventListener("click", organizeAll);
$("#reload-btn").addEventListener("click", reload);
$("#sort-btn").addEventListener("click", () => {
  state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
  $("#sort-btn").textContent = state.sortDir === "asc" ? "Time ↑" : "Time ↓";
  renderSidebar();
});
$("#hide-hidden").addEventListener("change", (e) => {
  state.hideHidden = e.target.checked;
  renderSidebar();
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
