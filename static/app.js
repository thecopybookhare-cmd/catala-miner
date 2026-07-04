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

// ---------- Anki badge ----------
async function refreshAnki() {
  const s = await api("/api/anki/status");
  const b = $("anki-badge");
  if (s.pending > 0) { b.textContent = `Anki: ${s.pending} en cua`; b.className = "badge pending"; }
  else if (s.up) { b.textContent = "Anki ✓"; b.className = "badge up"; }
  else { b.textContent = "Anki tancat"; b.className = "badge"; }
}
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
  if (r.has_sidecar_subs) $("sidecar-btn").hidden = false;
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

// ---------- player ----------
async function openSession(sid) {
  const s = await api("/api/sessions/" + sid);
  SESSION = s; SEGS = s.transcript; KNOWN = new Set(s.known_lemmas);
  $("home").hidden = true; $("player").hidden = false;
  $("video").src = s.media_url;
  renderSegs();
}
$("back").onclick = () => { $("player").hidden = true; $("home").hidden = false; $("card-panel").hidden = true; loadSessions(); };

$("transcribe-btn").onclick = async () => {
  const model = $("model-select").value;
  const { job_id } = await api(`/api/sessions/${SESSION.id}/transcribe`,
    { method: "POST", body: JSON.stringify({ model }) });
  const res = await pollJob(job_id, "Transcrivint… (la primera vegada descarrega el model)");
  if (res) openSession(SESSION.id);
};
$("sidecar-btn").onclick = async () => {
  const { job_id } = await api(`/api/sessions/${SESSION.id}/transcribe`,
    { method: "POST", body: JSON.stringify({ use_sidecar: true }) });
  const res = await pollJob(job_id, "Carregant subtítols…");
  if (res) openSession(SESSION.id);
};

function fmtTime(t) {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

const badge = (z) => (z >= 5 ? "common" : z >= 3.3 ? "medium" : "rare");

function renderSegs() {
  const el = $("subs");
  if (!SEGS.length) { el.innerHTML = '<p class="dim">Sense transcripció encara — prem 🎙️ Transcriure.</p>'; return; }
  el.innerHTML = SEGS.map((seg, i) => {
    const toks = (seg.tokens && seg.tokens.length)
      ? seg.tokens.map((t) => t.is_word
          ? `<span class="t ${KNOWN.has(t.lemma) ? "known" : ""} freq-${badge(t.zipf)}" data-l="${t.lemma}">${t.t}</span>`
          : `<span>${t.t}</span>`).join(" ")
      : seg.text;
    const low = seg.logprob < -1.0 ? " lowconf" : "";
    return `<div class="seg${low}" id="seg-${i}" data-i="${i}">
      <span class="time">${fmtTime(seg.start)}</span>${toks}</div>`;
  }).join("");
  for (const div of el.querySelectorAll(".seg")) {
    const i = +div.dataset.i;
    div.querySelector(".time").onclick = () => { $("video").currentTime = SEGS[i].start; $("video").play(); };
    for (const tok of div.querySelectorAll(".t"))
      tok.onclick = () => mine(i, window.getSelection().toString().trim() || tok.textContent);
  }
}

$("video").addEventListener("timeupdate", () => {
  const t = $("video").currentTime;
  const i = SEGS.findIndex((s) => t >= s.start && t <= s.end);
  document.querySelectorAll(".seg.active").forEach((d) => d.classList.remove("active"));
  if (i >= 0) {
    const div = $("seg-" + i);
    div.classList.add("active");
    div.scrollIntoView({ block: "center", behavior: "smooth" });
  }
});

document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") {
    if (e.key === "Enter" && !e.shiftKey && !$("card-panel").hidden) { e.preventDefault(); sendCard(); }
    return;
  }
  if ($("player").hidden) return;
  const v = $("video");
  const cur = SEGS.findIndex((s) => v.currentTime >= s.start && v.currentTime <= s.end);
  if (e.key === " ") { e.preventDefault(); v.paused ? v.play() : v.pause(); }
  if (e.key === "ArrowLeft") { e.preventDefault(); v.currentTime = SEGS[Math.max(0, cur - 1)]?.start ?? 0; }
  if (e.key === "ArrowRight") { e.preventDefault(); v.currentTime = SEGS[Math.min(SEGS.length - 1, cur + 1)]?.start ?? v.currentTime; }
  if (e.key === "a" && cur >= 0) { v.currentTime = SEGS[cur].start; v.play(); }
  if (e.key === "Enter" && !$("card-panel").hidden) sendCard();
  if (e.key === "Escape") $("card-panel").hidden = true;
});

// ---------- mining ----------
async function mine(segIndex, selection, padB = 0, padA = 0) {
  $("video").pause();
  PAD = { b: padB, a: padA };
  toast("Creant targeta…");
  const p = await api("/api/cards/preview", {
    method: "POST",
    body: JSON.stringify({ session_id: SESSION.id, segment_index: segIndex,
      selection, pad_before: padB, pad_after: padA }),
  });
  CARD = { ...p, session_id: SESSION.id, segment_index: segIndex };
  $("c-paraula").value = p.paraula;
  $("c-paraula-es").value = p.paraula_es;
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
  refreshAnki();
  toast(r.sent_now ? "✅ Targeta afegida a Anki" : "🕓 Targeta en cua (obre Anki per enviar-la)", r.sent_now ? "ok" : "err");
}
$("c-send").onclick = sendCard;

// ---------- init ----------
loadSessions();
refreshAnki();
