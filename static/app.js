const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" }, ...opts,
  });
  return r.json();
};
const toast = (msg, cls = "ok") => {
  const t = $("toast");
  t.textContent = msg; t.className = cls; t.hidden = false;
  setTimeout(() => (t.hidden = true), 2600);
};

let SESSION = null, SEGS = [], KNOWN = new Set(), CARD = null, PAD = { b: 0, a: 0 };
let CUR = -1;
let DUAL = false, AUTOPAUSE = false, HIDE_CA = false, HIDE_ES = false;
let POP = null;               // word popup state
let HOVER = null;             // {segIndex, text} of token under mouse (for Q)
const ES_CACHE = {};

// ---------- Anki badge with diagnosis ----------
async function refreshAnki() {
  const s = await api("/api/anki/status");
  const b = $("anki-badge");
  const q = s.pending > 0 ? `${s.pending} en cua · ` : "";
  if (s.up) { b.textContent = s.pending > 0 ? `Anki: enviant ${s.pending}…` : `Anki ✓ (:${s.port})`; b.className = "badge up"; }
  else if (s.reason === "squatted") { b.textContent = `⚠️ ${q}port ocupat — clica`; b.className = "badge err"; }
  else { b.textContent = q + "Anki tancat"; b.className = s.pending > 0 ? "badge pending" : "badge"; }
  b.dataset.reason = s.reason || "";
}
$("anki-badge").onclick = async () => {
  const reason = $("anki-badge").dataset.reason;
  let msg = "Port d'AnkiConnect (buit = automàtic 8765/8766/8767):";
  if (reason === "squatted")
    msg = "Un altre servei ocupa els ports 8765/8766 en aquest Mac.\n\nSolució: a Anki → Eines → Complements → AnkiConnect → Configuració, posa \"webBindPort\": 8767, reinicia Anki. L'app el detectarà sola (o escriu 8767 aquí sota).\n\nPort d'AnkiConnect:";
  const v = prompt(msg);
  if (v === null) return;
  const port = v.trim() === "" ? null : parseInt(v.trim(), 10);
  const r = await api("/api/anki/port", { method: "POST", body: JSON.stringify({ port }) });
  toast(r.port ? `✅ AnkiConnect trobat al port ${r.port}` : "Encara no trobo AnkiConnect", r.port ? "ok" : "err");
  refreshAnki();
};
setInterval(async () => { await api("/api/anki/flush", { method: "POST" }).catch(() => {}); refreshAnki(); }, 15000);

// ---------- home ----------
async function loadSessions() {
  const list = await api("/api/sessions");
  $("session-list").innerHTML = list.map((s) =>
    `<li data-id="${s.id}"><span>${s.title}</span>
     <span class="dim">${s.srt_source} · ${s.created_at.slice(0, 10)}</span></li>`).join("");
  for (const li of $("session-list").children)
    li.onclick = () => openSession(li.dataset.id);
}

$("file-input").onchange = async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("file", f);
  toast("Pujant arxiu…");
  const r = await fetch("/api/sessions/upload", { method: "POST", body: fd }).then((x) => x.json());
  await openSession(r.session_id);
};

$("yt-btn").onclick = async () => {
  const url = $("yt-url").value.trim();
  if (!url) return;
  const { job_id } = await api("/api/sessions/youtube", { method: "POST", body: JSON.stringify({ url }) });
  const res = await pollJob(job_id, "Descarregant de YouTube…");
  if (res) openSession(res.session_id);
};

// ---------- jobs ----------
async function pollJob(jid, label) {
  $("job-progress").hidden = false;
  $("job-msg").textContent = label;
  while (true) {
    const j = await api("/api/jobs/" + jid);
    $("job-progress").value = j.progress || 0;
    $("job-msg").textContent = j.message || label;
    if (j.status === "done") { $("job-progress").hidden = true; $("job-msg").textContent = ""; return j.result; }
    if (j.status === "error") { $("job-progress").hidden = true; toast("Error: " + j.message, "err"); return null; }
    await new Promise((r) => setTimeout(r, 800));
  }
}

// ---------- session ----------
async function openSession(sid) {
  const s = await api("/api/sessions/" + sid);
  SESSION = s; SEGS = s.transcript; KNOWN = new Set(s.known_lemmas);
  CUR = -1; POP = null; HOVER = null; $("word-pop").hidden = true;
  for (const k in ES_CACHE) delete ES_CACHE[k];
  SEGS.forEach((seg, i) => { if (seg.text_es) ES_CACHE[i] = seg.text_es; });
  $("home").hidden = true; $("player").hidden = false;
  $("video").src = s.media_url;
  renderSegs();
  renderOverlay();
}
$("back").onclick = () => {
  if (document.fullscreenElement) document.exitFullscreen();
  $("player").hidden = true; $("home").hidden = false;
  $("card-panel").hidden = true; $("word-pop").hidden = true;
  loadSessions();
};

$("transcribe-btn").onclick = async () => {
  const model = $("model-select").value;
  const { job_id } = await api(`/api/sessions/${SESSION.id}/transcribe`,
    { method: "POST", body: JSON.stringify({ model }) });
  const res = await pollJob(job_id, "Transcrivint… (la primera vegada descarrega el model)");
  if (res) openSession(SESSION.id);
};

$("subs-input").onchange = async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("file", f);
  const r = await fetch(`/api/sessions/${SESSION.id}/subtitles`, { method: "POST", body: fd }).then((x) => x.json());
  if (r.error) { toast(r.error, "err"); return; }
  toast(`📜 ${r.segments} subtítols carregats`);
  openSession(SESSION.id);
};

// ---------- toggles ----------
$("dual-btn").onclick = () => setDual(!DUAL);
$("autopause-btn").onclick = () => setAutopause(!AUTOPAUSE);
$("browser-btn").onclick = () => toggleBrowser();
$("fs-btn").onclick = () => toggleFullscreen();

function setDual(v) {
  DUAL = v;
  $("dual-btn").classList.toggle("on", v);
  $("overlay-es").hidden = !v || HIDE_ES;
  if (v) fillDual(CUR);
}
function setAutopause(v) {
  AUTOPAUSE = v;
  $("autopause-btn").classList.toggle("on", v);
}
function toggleBrowser() {
  const p = $("side-panel");
  p.hidden = !p.hidden;
  $("browser-btn").classList.toggle("on", !p.hidden);
  if (!p.hidden) scrollBrowserTo(CUR);
}
function toggleFullscreen() {
  const col = $("video-col");
  if (document.fullscreenElement) { document.exitFullscreen(); return; }
  if (col.classList.contains("fake-fs")) { col.classList.remove("fake-fs"); $("fs-btn").textContent = "⛶"; return; }
  const p = col.requestFullscreen ? col.requestFullscreen() : Promise.reject();
  Promise.resolve(p).catch(() => {
    // environment blocks native fullscreen: fill the window instead
    col.classList.add("fake-fs");
    $("fs-btn").textContent = "🗗";
  });
}
document.addEventListener("fullscreenchange", () => {
  $("fs-btn").textContent = document.fullscreenElement ? "🗗" : "⛶";
});

// ---------- rendering ----------
function fmtTime(t) {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}
const badge = (z) => (z >= 5 ? "common" : z >= 3.3 ? "medium" : "rare");

function tokenHtml(seg) {
  if (!(seg.tokens && seg.tokens.length)) return seg.text;
  return seg.tokens.map((t, k) => {
    const html = t.is_word
      ? `<span class="t ${KNOWN.has(t.lemma) ? "known" : ""} freq-${badge(t.zipf)}" data-l="${t.lemma}">${t.t}</span>`
      : `<span>${t.t}</span>`;
    return (k > 0 && t.is_word ? " " : "") + html;
  }).join("");
}

function bindTokenEvents(container, segIndex) {
  for (const tok of container.querySelectorAll(".t")) {
    tok.onclick = (ev) => {
      ev.stopPropagation();
      const sel = window.getSelection().toString().trim();
      openPopup(segIndex, sel || tok.textContent, tok);
    };
    tok.onmouseenter = () => { HOVER = { segIndex, text: tok.textContent, el: tok }; };
    tok.onmouseleave = () => { if (HOVER && HOVER.el === tok) HOVER = null; };
  }
}

function renderSegs() {
  const el = $("subs");
  if (!SEGS.length) { el.innerHTML = '<p class="dim">Sense transcripció — 🎙️ Transcriu o 📎 adjunta un .srt.</p>'; return; }
  el.innerHTML = SEGS.map((seg, i) => {
    const low = seg.logprob < -1.0 ? " lowconf" : "";
    return `<div class="seg${low}" id="seg-${i}" data-i="${i}">
      <span class="time">${fmtTime(seg.start)}</span>${tokenHtml(seg)}</div>`;
  }).join("");
  for (const div of el.querySelectorAll(".seg")) {
    const i = +div.dataset.i;
    div.querySelector(".time").onclick = () => { $("video").currentTime = SEGS[i].start; $("video").play(); };
    bindTokenEvents(div, i);
  }
}

function renderOverlay() {
  const ca = $("overlay-ca");
  if (CUR < 0 || !SEGS[CUR]) { ca.innerHTML = ""; $("overlay-es").textContent = ""; return; }
  const long = SEGS[CUR].text.length > 140;
  ca.classList.toggle("longtext", long);
  $("overlay-es").classList.toggle("longtext", long);
  ca.style.display = HIDE_CA ? "none" : "";
  ca.innerHTML = tokenHtml(SEGS[CUR]);
  bindTokenEvents(ca, CUR);
  if (DUAL && !HIDE_ES) fillDual(CUR);
}

async function fillDual(i) {
  const es = $("overlay-es");
  if (i < 0 || !SEGS[i]) { es.textContent = ""; return; }
  if (ES_CACHE[i] === undefined) {
    ES_CACHE[i] = "";
    const r = await api(`/api/sessions/${SESSION.id}/segments/${i}/translate`, { method: "POST" });
    ES_CACHE[i] = r.text_es || "";
  }
  if (i === CUR) es.textContent = ES_CACHE[i];
  for (const j of [i + 1, i + 2])
    if (j < SEGS.length && ES_CACHE[j] === undefined) {
      ES_CACHE[j] = "";
      api(`/api/sessions/${SESSION.id}/segments/${j}/translate`, { method: "POST" })
        .then((r) => { ES_CACHE[j] = r.text_es || ""; if (j === CUR) es.textContent = ES_CACHE[j]; });
    }
}

// scroll INSIDE the browser panel only — never the page (user complaint)
function scrollBrowserTo(i) {
  const panel = $("side-panel");
  if (panel.hidden || i < 0) return;
  const row = $("seg-" + i);
  if (!row) return;
  panel.scrollTop = row.offsetTop - panel.clientHeight / 2 + row.offsetHeight / 2;
}

// ---------- video wiring ----------
const V = $("video");
V.addEventListener("click", () => { V.paused ? V.play() : V.pause(); });
V.addEventListener("play", () => { $("play-btn").textContent = "⏸"; });
V.addEventListener("pause", () => { $("play-btn").textContent = "▶"; });
V.addEventListener("loadedmetadata", () => { $("time-dur").textContent = fmtTime(V.duration || 0); });
$("play-btn").onclick = () => { V.paused ? V.play() : V.pause(); };
$("prev-btn").onclick = () => gotoSeg(CUR - 1);
$("next-btn").onclick = () => gotoSeg(CUR + 1);
$("replay-btn").onclick = () => replaySeg();

function gotoSeg(i) {
  if (!SEGS.length) return;
  const j = Math.min(SEGS.length - 1, Math.max(0, i < 0 && CUR < 0 ? 0 : i));
  V.currentTime = SEGS[j].start + 0.01;
  V.play();
}
function replaySeg() {
  if (CUR < 0) return;
  V.currentTime = SEGS[CUR].start + 0.01;
  V.play();
}

let seeking = false;
$("seek").oninput = () => { seeking = true; };
$("seek").onchange = () => {
  V.currentTime = ($("seek").value / 1000) * (V.duration || 0);
  seeking = false;
};

V.addEventListener("timeupdate", () => {
  const t = V.currentTime;
  if (!seeking && V.duration) $("seek").value = Math.round((t / V.duration) * 1000);
  $("time-cur").textContent = fmtTime(t);
  const i = SEGS.findIndex((s) => t >= s.start && t <= s.end);
  if (AUTOPAUSE && !V.paused && CUR >= 0 && i !== CUR) {
    V.pause();
    V.currentTime = Math.max(SEGS[CUR].end - 0.02, SEGS[CUR].start);
    return;
  }
  if (i !== CUR) {
    CUR = i;
    document.querySelectorAll(".seg.active").forEach((d) => d.classList.remove("active"));
    if (i >= 0) $("seg-" + i)?.classList.add("active");
    scrollBrowserTo(i);
    renderOverlay();
  }
});

// ---------- word popup ----------
async function openPopup(segIndex, selection, anchorEl) {
  V.pause();
  if (POP && !$("word-pop").hidden && POP.selection === selection && POP.segIndex === segIndex) {
    closePopup();
    return;
  }
  POP = { segIndex, selection };
  $("wp-word").textContent = selection;
  $("wp-meta").textContent = "…";
  $("wp-senses").innerHTML = "";
  $("wp-word-es").textContent = "";
  $("wp-sentence-es").textContent = "";
  positionPopup(anchorEl);
  $("word-pop").hidden = false;

  const r = await api("/api/lookup", {
    method: "POST",
    body: JSON.stringify({ selection, sentence: SEGS[segIndex].text }),
  });
  if (!POP || POP.selection !== selection) return;
  POP.lookup = r;
  $("wp-meta").textContent = `${r.lemma} · ${r.pos || "?"} · ${r.freq_rank} (zipf ${r.zipf.toFixed(1)})`;
  $("wp-senses").innerHTML = (r.senses.length ? r.senses : [])
    .map((s) => `<span class="sense" data-es="${s.es}">${s.es} <small>${s.pos}</small></span>`).join("")
    || '<span class="dim" style="font-size:13px">— sense entrada al diccionari —</span>';
  for (const sp of $("wp-senses").querySelectorAll(".sense"))
    sp.onclick = () => { POP.chosen = sp.dataset.es; mineFromPopup(); };
  $("wp-word-es").textContent = r.word_es ? `→ ${r.word_es}` : "";
  $("wp-sentence-es").textContent = r.sentence_es || "";
}

function positionPopup(anchorEl) {
  const pop = $("word-pop");
  const rect = anchorEl.getBoundingClientRect();
  pop.hidden = false;
  const w = 300, h = pop.offsetHeight || 220;
  let x = Math.min(Math.max(8, rect.left + rect.width / 2 - w / 2), window.innerWidth - w - 8);
  let y = rect.top - h - 10;
  if (y < 8) y = Math.min(rect.bottom + 10, window.innerHeight - h - 8);
  pop.style.left = x + "px";
  pop.style.top = y + "px";
}

function closePopup() { $("word-pop").hidden = true; POP = null; }
$("wp-close").onclick = closePopup;
document.addEventListener("click", (e) => {
  if (!$("word-pop").hidden && !$("word-pop").contains(e.target) && !e.target.classList?.contains("t"))
    closePopup();
});
$("wp-replay").onclick = () => { if (POP) { V.currentTime = SEGS[POP.segIndex].start; V.play(); } };
$("wp-card").onclick = () => mineFromPopup();

function mineFromPopup() {
  if (!POP) return;
  const { segIndex, selection, chosen, lookup } = POP;
  closePopup();
  mine(segIndex, selection, 0, 0, { chosen, lookup });
}

// ---------- mining ----------
async function mine(segIndex, selection, padB = 0, padA = 0, extra = {}) {
  V.pause();
  PAD = { b: padB, a: padA };
  toast("Creant targeta…");
  const p = await api("/api/cards/preview", {
    method: "POST",
    body: JSON.stringify({ session_id: SESSION.id, segment_index: segIndex,
      selection, pad_before: padB, pad_after: padA }),
  });
  CARD = { ...p, session_id: SESSION.id, segment_index: segIndex };
  $("c-paraula").value = p.paraula;
  $("c-paraula-es").value = extra.chosen || p.paraula_es;
  $("c-frase").value = p.frase;
  $("c-frase-es").value = p.frase_es;
  $("c-meta").textContent = `${p.lema} · ${p.pos} · ${p.freq_rank} (zipf ${p.freq_zipf.toFixed(1)}) · ${p.font}`;
  $("senses").innerHTML = p.senses.map((s) =>
    `<span class="sense" data-es="${s.es}">${s.es} <small>${s.pos}</small></span>`).join("");
  for (const sp of $("senses").children)
    sp.onclick = () => { $("c-paraula-es").value = sp.dataset.es; };
  $("c-audio").src = p.audio_file ? "/media/" + p.audio_file : "";
  $("c-image").src = p.image_file ? "/media/" + p.image_file : "";
  $("card-panel").hidden = false;
  if (p.audio_file) $("c-audio").play().catch(() => {});
}

$("pad-before").onclick = () => CARD && mine(CARD.segment_index, $("c-paraula").value, PAD.b + 1, PAD.a);
$("pad-after").onclick = () => CARD && mine(CARD.segment_index, $("c-paraula").value, PAD.b, PAD.a + 1);
$("c-cancel").onclick = () => { $("card-panel").hidden = true; };

async function sendCard() {
  if (!CARD) return;
  const body = {
    session_id: CARD.session_id, segment_index: CARD.segment_index,
    paraula: $("c-paraula").value, lema: CARD.lema, pos: CARD.pos,
    paraula_es: $("c-paraula-es").value,
    frase: $("c-frase").value, frase_es: $("c-frase-es").value,
    freq_rank: CARD.freq_rank, audio_file: CARD.audio_file,
    image_file: CARD.image_file, font: CARD.font,
  };
  const r = await api("/api/cards", { method: "POST", body: JSON.stringify(body) });
  $("card-panel").hidden = true;
  KNOWN.add(CARD.lema);
  renderSegs();
  renderOverlay();
  refreshAnki();
  toast(r.sent_now ? "✅ Targeta afegida a Anki" : "🕓 Targeta en cua", r.sent_now ? "ok" : "err");
}
$("c-send").onclick = sendCard;

// ---------- Migaku keyboard map ----------
// A/← prev · D/→ next · S/↓ replay · W/↑ hide subs · shift+W hide ES ·
// G browser · C copy · Q mine hovered word · E dual · P auto-pause · F fullscreen
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") {
    if (e.key === "Enter" && !e.shiftKey && !$("card-panel").hidden) { e.preventDefault(); sendCard(); }
    return;
  }
  if ($("player").hidden) return;
  const k = e.key.toLowerCase();
  if (e.key === " ") { e.preventDefault(); V.paused ? V.play() : V.pause(); return; }
  if (k === "a" || e.key === "ArrowLeft") { e.preventDefault(); gotoSeg(CUR < 0 ? 0 : CUR - 1); }
  else if (k === "d" || e.key === "ArrowRight") { e.preventDefault(); gotoSeg(CUR < 0 ? 0 : CUR + 1); }
  else if (k === "s" || e.key === "ArrowDown") { e.preventDefault(); replaySeg(); }
  else if (k === "w" || e.key === "ArrowUp") {
    e.preventDefault();
    if (e.shiftKey) { HIDE_ES = !HIDE_ES; $("overlay-es").hidden = !DUAL || HIDE_ES; }
    else { HIDE_CA = !HIDE_CA; renderOverlay(); }
  }
  else if (k === "g") toggleBrowser();
  else if (k === "c" && CUR >= 0) { navigator.clipboard.writeText(SEGS[CUR].text).then(() => toast("📋 Copiat")); }
  else if (k === "q") {
    if (POP && !$("word-pop").hidden) mineFromPopup();
    else if (HOVER) mine(HOVER.segIndex, HOVER.text);
    else toast("Passa el ratolí per una paraula i prem Q", "err");
  }
  else if (k === "e") setDual(!DUAL);
  else if (k === "p") setAutopause(!AUTOPAUSE);
  else if (k === "f") toggleFullscreen();
  else if (e.key === "Enter" && !$("card-panel").hidden) sendCard();
  else if (e.key === "Escape") {
    closePopup(); $("card-panel").hidden = true;
    if ($("video-col").classList.contains("fake-fs")) { $("video-col").classList.remove("fake-fs"); $("fs-btn").textContent = "⛶"; }
  }
});

// ---------- init ----------
loadSessions();
refreshAnki();
