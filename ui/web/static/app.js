"use strict";
// VideoEditTool GUI フロントエンド。処理はサーバ(pipeline)に委譲し、ここは表示と操作のみ。

const $ = (id) => document.getElementById(id);
let STATE = null; // { media, candidates:[{...,enabled}], report }

function fmtTime(sec) {
  sec = Math.max(0, sec || 0);
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(1).padStart(4, "0");
  return `${m}:${s}`;
}

// 有効なカット区間の和集合の総和と、残す区間（補集合）を計算する。
function computeKeep(cuts, duration) {
  const active = cuts.filter((c) => c.enabled).map((c) => [c.start, c.end])
    .sort((a, b) => a[0] - b[0]);
  // 和集合
  const merged = [];
  for (const [s, e] of active) {
    if (merged.length && s <= merged[merged.length - 1][1]) {
      merged[merged.length - 1][1] = Math.max(merged[merged.length - 1][1], e);
    } else merged.push([Math.max(0, s), Math.min(e, duration)]);
  }
  // 補集合 = 残す
  const keep = [];
  let cur = 0;
  for (const [s, e] of merged) {
    if (s > cur) keep.push([cur, s]);
    cur = Math.max(cur, e);
  }
  if (cur < duration) keep.push([cur, duration]);
  const removed = merged.reduce((a, [s, e]) => a + (e - s), 0);
  return { keep, removed };
}

function pct(v, total) { return total > 0 ? (v / total) * 100 : 0; }

function renderMetrics() {
  const d = STATE.media.duration;
  const { keep, removed } = computeKeep(STATE.candidates, d);
  const kept = d - removed;
  const active = STATE.candidates.filter((c) => c.enabled).length;
  const tiles = [
    ["総尺", fmtTime(d)],
    ["残時間", fmtTime(kept)],
    ["削除率", `${Math.round(pct(removed, d))}%`],
    ["カット", `${active}`],
    ["残区間", `${keep.length}`],
  ];
  $("metrics").innerHTML = tiles
    .map(([k, v]) => `<div class="metric"><div class="v">${v}</div><div class="k">${k}</div></div>`)
    .join("");
  renderTimeline(keep);
}

function renderTimeline(keep) {
  const d = STATE.media.duration || 1;
  const tl = $("timeline");
  // 既存の cut ブロックを消して再描画（play ライン以外）。
  [...tl.querySelectorAll(".cut")].forEach((n) => n.remove());
  STATE.candidates.forEach((c) => {
    const el = document.createElement("div");
    el.className = "cut" + (c.enabled ? "" : " off");
    el.style.left = pct(c.start, d) + "%";
    el.style.width = pct(c.end - c.start, d) + "%";
    el.title = `${c.rule} ${fmtTime(c.start)}–${fmtTime(c.end)}`;
    el.onclick = (ev) => { ev.stopPropagation(); seek(c.start); };
    tl.appendChild(el);
  });
  // 目盛り
  const ruler = $("ruler");
  ruler.innerHTML = "";
  const ticks = 6;
  for (let i = 0; i <= ticks; i++) {
    const t = (d * i) / ticks;
    const sp = document.createElement("span");
    sp.style.left = pct(t, d) + "%";
    sp.textContent = fmtTime(t);
    ruler.appendChild(sp);
  }
}

function renderCandidates() {
  const box = $("cands");
  box.innerHTML = "";
  $("candcount").textContent = `(${STATE.candidates.length} 件)`;
  STATE.candidates.forEach((c, i) => {
    const row = document.createElement("div");
    row.className = "cand";
    row.innerHTML =
      `<input type="checkbox" ${c.enabled ? "checked" : ""} data-i="${i}">` +
      `<span class="badge">${c.rule}</span>` +
      `<span class="tc">${fmtTime(c.start)}–${fmtTime(c.end)}</span>` +
      `<span class="reason">${escapeHtml(c.reason || "")}</span>` +
      `<button class="seek" data-seek="${c.start}">▶ 頭出し</button>`;
    box.appendChild(row);
  });
  box.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    cb.onchange = () => { STATE.candidates[+cb.dataset.i].enabled = cb.checked; renderMetrics(); renderTimeline_update(); };
  });
  box.querySelectorAll("button[data-seek]").forEach((b) => {
    b.onclick = () => seek(+b.dataset.seek);
  });
}

function renderTimeline_update() {
  const { keep } = computeKeep(STATE.candidates, STATE.media.duration);
  renderTimeline(keep);
}

function renderWarnings() {
  const w = STATE.report.warnings || [];
  $("warnings").innerHTML = w.map((m) => `<div class="warn">⚠ ${escapeHtml(m)}</div>`).join("");
}

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function seek(t) { const v = $("video"); if (v.src) { v.currentTime = t; v.play().catch(() => {}); } }

async function loadWaveform(path) {
  try {
    const res = await fetch(`/api/waveform?path=${encodeURIComponent(path)}&buckets=600`);
    const data = await res.json();
    if (res.ok && Array.isArray(data.peaks)) drawWaveform(data.peaks);
  } catch (_) { /* 波形は装飾。失敗しても編集は続行可能 */ }
}

function drawWaveform(peaks) {
  const cv = $("wave");
  const rect = cv.getBoundingClientRect();
  const w = Math.max(1, Math.floor(rect.width));
  const h = Math.max(1, Math.floor(rect.height));
  cv.width = w; cv.height = h;
  const ctx = cv.getContext("2d");
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#ffffff";
  const n = peaks.length;
  for (let x = 0; x < w; x++) {
    const p = peaks[Math.floor((x / w) * n)] || 0;
    const bh = Math.max(1, p * h);
    ctx.fillRect(x, (h - bh) / 2, 1, bh);
  }
}

async function analyze() {
  const path = $("path").value.trim();
  const profile = $("profile").value;
  if (!path) { $("status").textContent = "パスを入力してください。"; return; }
  // 検出オプション。フィラー/重複は文字起こしが前提なので自動で有効化。
  const rules = [];
  if ($("r_silence").checked) rules.push("silence");
  if ($("r_filler").checked) rules.push("filler");
  if ($("r_duplicate").checked) rules.push("duplicate");
  const needTranscript = $("r_transcript").checked || $("r_filler").checked || $("r_duplicate").checked;
  if (needTranscript) $("r_transcript").checked = true;

  $("analyze").disabled = true;
  $("status").textContent = needTranscript
    ? "解析中…（文字起こしはモデルDL/推論で時間がかかります）"
    : "解析中…";
  try {
    const url = `/api/analyze?path=${encodeURIComponent(path)}&profile=${encodeURIComponent(profile)}`
      + `&rules=${encodeURIComponent(rules.join(","))}&transcript=${needTranscript ? "1" : "0"}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "解析に失敗しました");
    STATE = {
      media: data.media,
      report: data.report,
      candidates: data.candidates.map((c) => ({ ...c, enabled: true })),
    };
    $("video").src = `/media?path=${encodeURIComponent(path)}`;
    $("result").classList.remove("hidden");
    $("status").textContent = `解析完了: ${data.media.name}`;
    renderCandidates(); renderMetrics(); renderWarnings();
    loadWaveform(path); // タイムライン背景に波形（装飾・非同期）
  } catch (e) {
    $("status").textContent = "エラー: " + e.message;
  } finally {
    $("analyze").disabled = false;
  }
}

async function doExport() {
  if (!STATE) return;
  $("export").disabled = true;
  $("exportout").textContent = "書き出し中…";
  try {
    const body = {
      path: STATE.media.path,
      profile: $("profile").value || null,
      format: $("fmt").value,
      render: $("render").checked,
      enabled_indices: STATE.candidates.filter((c) => c.enabled).map((c) => c.index),
    };
    const res = await fetch("/api/export", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "書き出しに失敗しました");
    $("exportout").innerHTML = "出力:<br>" + data.outputs.map(escapeHtml).join("<br>");
  } catch (e) {
    $("exportout").textContent = "エラー: " + e.message;
  } finally {
    $("export").disabled = false;
  }
}

// 再生位置に合わせて playhead を動かす。
$("video").addEventListener("timeupdate", () => {
  if (!STATE) return;
  $("play").style.left = pct($("video").currentTime, STATE.media.duration) + "%";
});
// タイムラインクリックでシーク。
$("timeline").addEventListener("click", (ev) => {
  if (!STATE) return;
  const rect = ev.currentTarget.getBoundingClientRect();
  seek(((ev.clientX - rect.left) / rect.width) * STATE.media.duration);
});
$("analyze").onclick = analyze;
$("export").onclick = doExport;
$("path").addEventListener("keydown", (e) => { if (e.key === "Enter") analyze(); });
