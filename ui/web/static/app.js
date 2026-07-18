"use strict";
// VideoEditTool GUI フロントエンド。複数動画を1プロジェクトとして扱い、
// 動画ごとに解析結果と手編集状態を保持する。処理はサーバ(pipeline)に委譲。

const $ = (id) => document.getElementById(id);

// 動画1件: { path, name, media, cuts:[{start,end,rule,reason,enabled}], transcript,
//            transcribed, contentRules, report, status:'new'|'analyzing'|'done', edited:bool }
let PROJECT = { videos: [], cur: -1 };
let analyzing = false;
function cur() { return PROJECT.cur >= 0 ? PROJECT.videos[PROJECT.cur] : null; }
function markEdited() { const v = cur(); if (v && v.status === "done") { v.edited = true; renderVideoList(); } }

function fmtTime(sec) {
  sec = Math.max(0, sec || 0);
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}`;
}
function pct(v, total) { return total > 0 ? (v / total) * 100 : 0; }
function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
// 語を読みやすく結合（英語などは空白、日本語は詰める）。
function joinWords(texts) {
  let out = "";
  for (const t of texts) {
    if (out && /[0-9A-Za-z]$/.test(out) && /^[0-9A-Za-z]/.test(t)) out += " " + t;
    else out += t;
  }
  return out;
}

// 有効カットの和集合の総和と、残す区間（補集合）。
function computeKeep(cuts, duration) {
  const active = cuts.filter((c) => c.enabled).map((c) => [c.start, c.end]).sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const [s, e] of active) {
    if (merged.length && s <= merged[merged.length - 1][1]) merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], e);
    else merged.push([Math.max(0, s), Math.min(e, duration)]);
  }
  const keep = []; let curp = 0;
  for (const [s, e] of merged) { if (s > curp) keep.push([curp, s]); curp = Math.max(curp, e); }
  if (curp < duration) keep.push([curp, duration]);
  return { keep, removed: merged.reduce((a, [s, e]) => a + (e - s), 0) };
}

// ---------- 動画リスト ----------
function renderVideoList() {
  const box = $("videolist");
  box.innerHTML = "";
  PROJECT.videos.forEach((v, i) => {
    const st = v.status === "analyzing" ? '<span class="st run">解析中…</span>'
      : v.status === "done" ? `<span class="st ok">解析済み${v.edited ? "・編集あり" : ""}</span>`
        : '<span class="st">未解析</span>';
    const el = document.createElement("div");
    el.className = "vitem" + (i === PROJECT.cur ? " sel" : "");
    el.innerHTML = `<span class="nm" title="${escapeHtml(v.path)}">${escapeHtml(v.name)}</span>${st}`
      + `<button class="rm" data-i="${i}" title="リストから外す">✕</button>`;
    el.onclick = (ev) => { if (ev.target.classList.contains("rm")) return; selectVideo(i); };
    box.appendChild(el);
  });
  box.querySelectorAll(".rm").forEach((b) => { b.onclick = () => removeVideo(+b.dataset.i); });
}

function selectVideo(i) {
  if (analyzing) { $("status").textContent = "解析中は切り替えできません。完了までお待ちください。"; return; }
  PROJECT.cur = i;
  renderVideoList();
  showVideo();
}

function removeVideo(i) {
  if (analyzing) return;
  PROJECT.videos.splice(i, 1);
  if (PROJECT.cur >= PROJECT.videos.length) PROJECT.cur = PROJECT.videos.length - 1;
  renderVideoList();
  showVideo();
}

function addVideo(path, name) {
  // 既に同じパスがあれば選択のみ。
  const idx = PROJECT.videos.findIndex((v) => v.path === path);
  if (idx >= 0) { PROJECT.cur = idx; }
  else {
    PROJECT.videos.push({ path, name: name || path.split(/[\\/]/).pop(), cuts: [], status: "new", edited: false });
    PROJECT.cur = PROJECT.videos.length - 1;
  }
  renderVideoList();
  showVideo();
}

// 選択中動画の内容を画面へ反映。
function showVideo() {
  const v = cur();
  if (!v) { $("result").classList.add("hidden"); return; }
  $("result").classList.remove("hidden");
  $("video").src = `/media?path=${encodeURIComponent(v.path)}`;
  ZOOM = 1; $("tlinner").style.width = "100%"; $("zoomlbl").textContent = "100%";
  if (v.status === "done") {
    refresh(); renderWarnings(); renderTranscript();
    loadWaveform(v.path);
    $("status").textContent = `${v.name}（解析済み${v.edited ? "・編集あり" : ""}）`;
  } else {
    // 未解析: プレビューのみ。カット/メトリクスは空。
    v.cuts = v.cuts || [];
    refresh(); $("warnings").innerHTML = ""; $("transcript").innerHTML = "";
    $("status").textContent = `${v.name} — 検出項目を選んで「解析」を押してください`;
  }
}

// ---------- 表示 ----------
function renderMetrics() {
  const v = cur(); if (!v) return;
  const d = v.media ? v.media.duration : 0;
  const { keep, removed } = computeKeep(v.cuts, d);
  const tiles = [
    ["総尺", fmtTime(d)], ["残時間", fmtTime(d - removed)],
    ["削除率", `${Math.round(pct(removed, d))}%`],
    ["カット", `${v.cuts.filter((c) => c.enabled).length}`], ["残区間", `${keep.length}`],
  ];
  $("metrics").innerHTML = tiles.map(([k, val]) => `<div class="metric"><div class="v">${val}</div><div class="k">${k}</div></div>`).join("");
}

function renderTimeline() {
  const v = cur(); if (!v || !v.media) return;
  const d = v.media.duration || 1;
  const tl = $("timeline");
  [...tl.querySelectorAll(".cut")].forEach((n) => n.remove());
  v.cuts.forEach((c, i) => {
    if (!c.enabled) return;
    const el = document.createElement("div");
    el.className = "cut";
    el.style.left = pct(c.start, d) + "%";
    el.style.width = pct(Math.max(0.001, c.end - c.start), d) + "%";
    el.title = `${c.rule} ${fmtTime(c.start)}–${fmtTime(c.end)}（ドラッグ移動 / 端で伸縮 / ダブルクリックで削除）`;
    el.innerHTML = `<div class="h l" data-i="${i}" data-edge="l"></div><div class="h r" data-i="${i}" data-edge="r"></div>`;
    el.addEventListener("pointerdown", (ev) => startDrag(ev, i, ev.target.dataset.edge || "move"));
    el.addEventListener("dblclick", (ev) => { ev.stopPropagation(); pushHistory(); v.cuts.splice(i, 1); markEdited(); refresh(); });
    tl.appendChild(el);
  });
  const ruler = $("ruler"); ruler.innerHTML = "";
  for (let i = 0; i <= 6; i++) {
    const t = (d * i) / 6;
    const sp = document.createElement("span");
    sp.style.left = pct(t, d) + "%"; sp.textContent = fmtTime(t);
    ruler.appendChild(sp);
  }
}

// カット区間に重なる文字起こしを取り出す（対応箇所の確認用）。
function wordsInRange(start, end) {
  const v = cur(); if (!v || !v.words) return "";
  const hit = v.words.filter((w) => w.start < end && w.end > start).map((w) => w.text);
  return hit.length ? joinWords(hit) : "";
}

function renderCuts() {
  const v = cur(); if (!v) return;
  const box = $("cands"); box.innerHTML = "";
  $("candcount").textContent = `(${v.cuts.length} 件)`;
  v.cuts.forEach((c, i) => {
    const row = document.createElement("div");
    row.className = "cand";
    const snip = wordsInRange(c.start, c.end);
    const snipHtml = v.words && v.words.length
      ? `<span class="reason" style="opacity:.85;">${snip ? "「" + escapeHtml(snip) + "」" : "（発話なし）"}</span>`
      : `<span class="reason">${escapeHtml(c.reason || "")}</span>`;
    row.innerHTML =
      `<input type="checkbox" ${c.enabled ? "checked" : ""} data-i="${i}" title="有効/無効">` +
      `<span class="badge">${escapeHtml(c.rule)}</span>` +
      `<input class="t" type="number" step="0.05" min="0" value="${c.start.toFixed(2)}" data-i="${i}" data-f="start">` +
      `<span style="color:var(--muted)">–</span>` +
      `<input class="t" type="number" step="0.05" min="0" value="${c.end.toFixed(2)}" data-i="${i}" data-f="end">` +
      snipHtml +
      `<button class="seek" data-seek="${c.start}">▶</button>` +
      `<button class="del" data-i="${i}" title="削除">✕</button>`;
    box.appendChild(row);
  });
  box.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    cb.onchange = () => { pushHistory(); v.cuts[+cb.dataset.i].enabled = cb.checked; markEdited(); renderTimeline(); renderMetrics(); };
  });
  box.querySelectorAll("input.t").forEach((inp) => {
    inp.onchange = () => {
      pushHistory();
      const c = v.cuts[+inp.dataset.i];
      c[inp.dataset.f] = Math.max(0, Math.min(v.media.duration, parseFloat(inp.value) || 0));
      if (c.end <= c.start) c.end = Math.min(v.media.duration, c.start + 0.1);
      markEdited(); refresh();
    };
  });
  box.querySelectorAll("button[data-seek]").forEach((b) => { b.onclick = () => seek(+b.dataset.seek); });
  box.querySelectorAll("button.del").forEach((b) => { b.onclick = () => { pushHistory(); v.cuts.splice(+b.dataset.i, 1); markEdited(); refresh(); }; });
}

function refresh() { renderCuts(); renderTimeline(); renderMetrics(); renderAutoRef(); renderWordTrack(); updateUndoBtn(); }

// ---------- 波形ズーム ----------
let ZOOM = 1;
function applyZoom() {
  ZOOM = Math.max(1, Math.min(30, ZOOM));
  $("tlinner").style.width = (ZOOM * 100) + "%";
  $("zoomlbl").textContent = Math.round(ZOOM * 100) + "%";
  const v = cur();
  if (v && v._peaks) drawWaveform(v._peaks);  // 幅が変わったので波形を再描画
  renderTimeline(); renderWordTrack(); renderAutoRef();
}

// ---------- 文字起こしの単語トラック（波形の下に時間軸で並べる） ----------
function isInActiveCut(t) {
  const v = cur();
  return v.cuts.some((c) => c.enabled && t >= c.start && t < c.end);
}
function renderWordTrack() {
  const v = cur(); const box = $("wordtrack");
  if (!v || !v.media || !v.words || !v.words.length) { box.innerHTML = ""; return; }
  const d = v.media.duration || 1;
  box.innerHTML = v.words.map((w) => {
    const mid = (w.start + w.end) / 2;
    const cls = isInActiveCut(mid) ? "w cutword" : "w";
    return `<span class="${cls}" style="left:${pct(w.start, d)}%;" data-t="${w.start}" title="${fmtTime(w.start)}">${escapeHtml(w.text)}</span>`;
  }).join("");
  box.querySelectorAll(".w").forEach((el) => { el.onclick = () => seek(+el.dataset.t); });
}

// ---------- Undo履歴 / 自動カットの別枠保存 ----------
function pushHistory() {
  const v = cur(); if (!v) return;
  v.history = v.history || [];
  v.history.push(JSON.stringify(v.cuts));
  if (v.history.length > 100) v.history.shift();
  updateUndoBtn();
}
function undo() {
  const v = cur(); if (!v || !v.history || !v.history.length) return;
  v.cuts = JSON.parse(v.history.pop());
  markEdited(); refresh();
}
function updateUndoBtn() {
  const v = cur();
  $("undo").disabled = !(v && v.history && v.history.length);
}
function resetToAuto() {
  const v = cur(); if (!v || !v.autoCuts) return;
  if (!confirm("手編集を破棄して、自動検出したカットに戻しますか？")) return;
  pushHistory();
  v.cuts = v.autoCuts.map((c) => ({ ...c }));
  v.edited = false; renderVideoList(); refresh();
}
// 自動検出カットの参照バンド（元カットとの二段表示）。
function renderAutoRef() {
  const v = cur(); const box = $("autoref");
  if (!v || !v.media || !v.autoCuts) { box.innerHTML = ""; return; }
  const d = v.media.duration || 1;
  box.innerHTML = v.autoCuts.map((c) =>
    `<div style="position:absolute;top:0;height:100%;left:${pct(c.start, d)}%;`
    + `width:${pct(Math.max(0.001, c.end - c.start), d)}%;background:var(--cut);opacity:.5;"`
    + ` title="自動: ${c.rule} ${fmtTime(c.start)}–${fmtTime(c.end)}"></div>`).join("");
}

function renderWarnings() {
  const v = cur(); const w = (v && v.report && v.report.warnings) || [];
  $("warnings").innerHTML = w.map((m) => `<div class="warn">⚠ ${escapeHtml(m)}</div>`).join("");
}

function renderTranscript() {
  const v = cur(); const box = $("transcript");
  if (!v || !v.contentRules || v.contentRules.length === 0) { box.innerHTML = ""; return; }
  const labels = { filler: "フィラー", duplicate: "重複", restate: "言い直し" };
  const zero = v.contentRules.filter((r) => !v.cuts.some((c) => c.rule === r));
  let html = "";
  if (!v.transcribed) html += `<div class="warn">⚠ 音声が無い/文字起こしできませんでした。</div>`;
  else if (zero.length) html += `<div>ℹ️ ${zero.map((r) => labels[r] || r).join("・")}に該当する箇所は見つかりませんでした。（下の文字起こしをご確認ください）</div>`;
  if (v.transcript) html += `<div style="margin-top:.3rem;"><b>文字起こし:</b> ${escapeHtml(v.transcript)}</div>`;
  box.innerHTML = html;
}

function seek(t) { const el = $("video"); if (el.src) { el.currentTime = t; el.play().catch(() => {}); } }

// ---------- 解析中オーバーレイ ----------
let _busyTimer = null;
function showBusy(msg, note) {
  $("busynote").textContent = note || "";
  $("busyoverlay").classList.remove("hidden");
  $("result").classList.add("busy");
  const t0 = Date.now();
  const paint = () => { $("busytext").textContent = `${msg}（${Math.floor((Date.now() - t0) / 1000)}秒）`; };
  paint(); _busyTimer = setInterval(paint, 1000);
}
function hideBusy() { if (_busyTimer) { clearInterval(_busyTimer); _busyTimer = null; } $("busyoverlay").classList.add("hidden"); $("result").classList.remove("busy"); }

async function loadWaveform(path) {
  try {
    const res = await fetch(`/api/waveform?path=${encodeURIComponent(path)}&buckets=1200`);
    const data = await res.json();
    if (res.ok && Array.isArray(data.peaks)) { const v = cur(); if (v) v._peaks = data.peaks; drawWaveform(data.peaks); }
  } catch (_) { /* 波形は装飾 */ }
}
function drawWaveform(peaks) {
  const cv = $("wave"); const rect = cv.getBoundingClientRect();
  const w = Math.max(1, Math.floor(rect.width)), h = Math.max(1, Math.floor(rect.height));
  cv.width = w; cv.height = h;
  const ctx = cv.getContext("2d"); ctx.clearRect(0, 0, w, h); ctx.fillStyle = "#ffffff";
  const n = peaks.length;
  for (let x = 0; x < w; x++) { const p = peaks[Math.floor((x / w) * n)] || 0; const bh = Math.max(1, p * h); ctx.fillRect(x, (h - bh) / 2, 1, bh); }
}

// ---------- 解析 ----------
async function analyze() {
  if (analyzing) return;
  // パス欄に手入力があれば動画として追加。
  const typed = $("path").value.trim().replace(/^["']|["']$/g, "").trim();
  if (typed) { $("path").value = ""; addVideo(typed); }
  const v = cur();
  if (!v) { $("status").textContent = "動画を追加してください（ドロップ / 選択 / お試し動画）。"; return; }

  const rules = [];
  ["silence", "tempo", "filler", "duplicate", "restate"].forEach((r) => { if ($("r_" + r).checked) rules.push(r); });
  const contentRules = ["filler", "duplicate", "restate"].filter((r) => rules.includes(r));
  const needTranscript = contentRules.length > 0;
  const lang = $("lang").value;

  // 編集済みの動画を再解析するときは確認（編集の上書き防止）。
  if (v.status === "done" && v.edited && !confirm(`「${v.name}」には手編集があります。破棄して再解析しますか？`)) return;

  analyzing = true; v.status = "analyzing"; renderVideoList();
  $("analyze").disabled = true;
  showBusy("解析中", needTranscript ? "文字起こしを使用中。初回はモデル取得で数分かかることがあります。" : "この動画を解析しています。");
  try {
    const url = `/api/analyze?path=${encodeURIComponent(v.path)}&profile=${encodeURIComponent($("profile").value)}`
      + `&rules=${encodeURIComponent(rules.join(","))}&transcript=${needTranscript ? "1" : "0"}&lang=${encodeURIComponent(lang)}`
      + `&model=${encodeURIComponent($("model").value)}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "解析に失敗しました");
    v.media = data.media; v.report = data.report;
    v.transcript = data.transcript || ""; v.transcribed = !!data.transcribed;
    v.words = data.words || [];
    v.contentRules = contentRules;
    v.cuts = data.candidates.map((c) => ({ start: c.start, end: c.end, rule: c.rule, reason: c.reason || "", enabled: true }));
    v.autoCuts = v.cuts.map((c) => ({ ...c }));  // 自動検出結果を別枠で保存（戻す用）
    v.history = [];
    v.status = "done"; v.edited = false;
    hideBusy();
    showVideo();
    if (v.cuts.length === 0) {
      $("status").textContent = rules.length === 0
        ? "検出項目が選ばれていません。項目を選ぶか「＋カット追加」で手動編集できます。"
        : `解析完了: ${v.name} — 自動カットは0件でした（手動で追加できます）。`;
    } else $("status").textContent = `解析完了: ${v.name}（カット${v.cuts.length}件）`;
  } catch (e) {
    v.status = v.media ? "done" : "new";
    hideBusy();
    $("status").textContent = "エラー: " + e.message;
  } finally {
    analyzing = false; $("analyze").disabled = false; renderVideoList();
  }
}

// ---------- 書き出し ----------
async function doExport() {
  const v = cur();
  if (!v || v.status !== "done") { $("exportout").textContent = "先に解析してください。"; return; }
  $("export").disabled = true;
  $("exportout").innerHTML = `<span class="spin"></span>書き出し中…` + ($("render").checked ? "（実カット動画は時間がかかります）" : "");
  try {
    const body = {
      path: v.path, profile: $("profile").value || null, format: $("fmt").value, render: $("render").checked,
      output_dir: $("outdir").value.trim().replace(/^["']|["']$/g, "").trim() || null,
      cuts: v.cuts.filter((c) => c.enabled).map((c) => ({ start: c.start, end: c.end })),
    };
    const res = await fetch("/api/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "書き出しに失敗しました");
    $("exportout").innerHTML = "出力:<br>" + data.outputs.map(escapeHtml).join("<br>");
  } catch (e) { $("exportout").textContent = "エラー: " + e.message; }
  finally { $("export").disabled = false; }
}

// ---------- タイムライン上のドラッグ編集 ----------
let _drag = null;
function _timeAtX(clientX) {
  const v = cur(); const r = $("timeline").getBoundingClientRect();
  return Math.max(0, Math.min(v.media.duration, ((clientX - r.left) / r.width) * v.media.duration));
}
function startDrag(ev, i, mode) {
  if (analyzing) return;
  ev.preventDefault(); ev.stopPropagation();
  const c = cur().cuts[i];
  _drag = { i, mode, t0: _timeAtX(ev.clientX), s0: c.start, e0: c.end };
  window.addEventListener("pointermove", onDrag);
  window.addEventListener("pointerup", endDrag, { once: true });
}
function onDrag(ev) {
  if (!_drag) return;
  if (!_drag.pushed) { pushHistory(); _drag.pushed = true; }  // 最初の移動時だけ履歴に積む
  const v = cur(); const c = v.cuts[_drag.i]; const D = v.media.duration;
  const dt = _timeAtX(ev.clientX) - _drag.t0;
  if (_drag.mode === "l") c.start = Math.max(0, Math.min(_drag.e0 - 0.05, _drag.s0 + dt));
  else if (_drag.mode === "r") c.end = Math.min(D, Math.max(_drag.s0 + 0.05, _drag.e0 + dt));
  else { const len = _drag.e0 - _drag.s0; const ns = Math.max(0, Math.min(D - len, _drag.s0 + dt)); c.start = ns; c.end = ns + len; }
  renderTimeline(); renderMetrics();
}
function endDrag() { window.removeEventListener("pointermove", onDrag); if (_drag) { markEdited(); renderCuts(); } _drag = null; }

// ---------- イベント ----------
$("video").addEventListener("timeupdate", () => {
  const v = cur(); if (!v || !v.media) return;
  const el = $("video");
  if ($("preview").checked) {
    const t = el.currentTime;
    for (const c of v.cuts) { if (c.enabled && t >= c.start && t < c.end - 0.02) { el.currentTime = c.end; break; } }
  }
  $("play").style.left = pct(el.currentTime, v.media.duration) + "%";
});

$("timeline").addEventListener("pointerdown", (ev) => {
  const v = cur(); if (!v || !v.media || analyzing || ev.target.closest(".cut")) return;
  const t0 = _timeAtX(ev.clientX); let created = null, moved = false;
  const mv = (e) => {
    const t = _timeAtX(e.clientX);
    if (!moved && Math.abs(t - t0) < 0.08) return;
    moved = true;
    if (!created) { pushHistory(); created = { start: t0, end: t0, rule: "manual", reason: "手動カット", enabled: true }; v.cuts.push(created); }
    created.start = Math.min(t0, t); created.end = Math.max(t0, t);
    renderTimeline(); renderMetrics();
  };
  const up = () => { window.removeEventListener("pointermove", mv); if (!moved) seek(t0); else { markEdited(); renderCuts(); } };
  window.addEventListener("pointermove", mv);
  window.addEventListener("pointerup", up, { once: true });
});

$("addcut").onclick = () => {
  const v = cur(); if (!v || !v.media) return;
  pushHistory();
  const t = $("video").currentTime || 0, D = v.media.duration;
  const s = Math.max(0, Math.min(D - 0.2, t));
  v.cuts.push({ start: s, end: Math.min(D, s + 1.0), rule: "manual", reason: "手動カット", enabled: true });
  markEdited(); refresh();
};
$("undo").onclick = undo;
$("resetauto").onclick = resetToAuto;
$("zoomin").onclick = () => { ZOOM *= 1.6; applyZoom(); };
$("zoomout").onclick = () => { ZOOM /= 1.6; applyZoom(); };

$("analyze").onclick = analyze;
$("export").onclick = doExport;
$("path").addEventListener("keydown", (e) => { if (e.key === "Enter") analyze(); });

// プロファイルの説明を画面に表示。
const PROFILE_DESC = {
  "": "既定の設定で解析します。",
  youtube: "テンポ重視。無音を強めにカットし、間を詰めます（vlog/解説向け）。",
  interview: "保守的。自然な間を残し、長い沈黙のみカットします（対談/インタビュー向け）。",
};
function updateProfDesc() { $("profdesc").textContent = PROFILE_DESC[$("profile").value] || ""; }
$("profile").addEventListener("change", updateProfDesc);
updateProfDesc();

// ---------- 動画の追加（アップロード・D&D・お試し） ----------
async function uploadFiles(files) {
  for (const file of files) {
    $("status").textContent = `読み込み中… ${file.name}`;
    try {
      const res = await fetch(`/api/upload?name=${encodeURIComponent(file.name)}`, { method: "POST", body: file });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "読み込み失敗");
      addVideo(data.path, file.name);
    } catch (e) { $("status").textContent = `エラー(${file.name}): ` + e.message; }
  }
  $("status").textContent = `${PROJECT.videos.length} 本の動画を読み込みました。項目を選んで「解析」を押してください。`;
}

$("pick").onclick = () => $("file").click();
$("file").addEventListener("change", (e) => { if (e.target.files.length) uploadFiles([...e.target.files]); });

const drop = $("drop");
["dragover", "dragenter"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.style.borderColor = "var(--accent)"; }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.style.borderColor = "var(--border)"; }));
drop.addEventListener("drop", (e) => { if (e.dataTransfer.files.length) uploadFiles([...e.dataTransfer.files]); });

(async () => {
  try {
    const res = await fetch("/api/drive"); const data = await res.json();
    if (res.ok && data.roots && data.roots.length) {
      const root = data.roots[0], btn = $("usedrive");
      btn.style.display = ""; btn.title = root;
      btn.onclick = () => { $("outdir").value = root + "\\VideoEditTool出力"; };
    }
  } catch (_) { /* Drive未導入 */ }
})();

$("fetchurl").onclick = async () => {
  const url = $("url").value.trim();
  if (!url) { $("status").textContent = "URLを入力してください。"; return; }
  $("fetchurl").disabled = true;
  const t0 = Date.now();
  const tick = setInterval(() => { $("status").innerHTML = `<span class="spin"></span>URLから取り込み中…（${Math.floor((Date.now() - t0) / 1000)}秒）`; }, 500);
  try {
    const res = await fetch("/api/fetch_url", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "取り込みに失敗しました");
    clearInterval(tick);
    addVideo(data.path, data.name);
    $("url").value = "";
    $("status").textContent = `取り込み完了: ${data.name} → 「解析」を押してください`;
  } catch (e) { clearInterval(tick); $("status").textContent = "エラー: " + e.message; }
  finally { $("fetchurl").disabled = false; }
};

$("sample").onclick = async () => {
  $("status").textContent = "お試し動画を作成中…";
  try {
    const res = await fetch("/api/make_sample", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "作成失敗");
    addVideo(data.path, "sample.mp4");
    $("status").textContent = "お試し動画を追加しました → 「解析」を押してください";
  } catch (e) { $("status").textContent = "エラー: " + e.message; }
};
