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

// 文字起こし本文と、内容ルールが0件だった理由を表示（「空振りの無言」を防ぐ）。
function renderTranscript() {
  const box = $("transcript");
  if (!STATE.contentRules || STATE.contentRules.length === 0) { box.innerHTML = ""; return; }
  const labels = { filler: "フィラー", duplicate: "重複", restate: "言い直し" };
  const zero = STATE.contentRules.filter(
    (r) => !STATE.candidates.some((c) => c.rule === r)
  );
  let html = "";
  if (!STATE.transcribed) {
    html += `<div class="warn">⚠ 音声が無い/文字起こしできませんでした。</div>`;
  } else if (zero.length) {
    html += `<div>ℹ️ ${zero.map((r) => labels[r] || r).join("・")}に該当する箇所は見つかりませんでした。`
      + `（下の文字起こし結果をご確認ください）</div>`;
  }
  if (STATE.transcript) {
    html += `<div style="margin-top:.3rem;"><b>文字起こし:</b> ${escapeHtml(STATE.transcript)}</div>`;
  }
  box.innerHTML = html;
}

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function seek(t) { const v = $("video"); if (v.src) { v.currentTime = t; v.play().catch(() => {}); } }

// 処理中インジケータ（スピナー＋経過秒）。同期処理でも「固まっていない」ことを示す。
let _busyTimer = null;
function startBusy(msg, note) {
  const t0 = Date.now();
  const paint = () => {
    const sec = Math.floor((Date.now() - t0) / 1000);
    $("status").innerHTML = `<span class="spin"></span>${escapeHtml(msg)}（${sec}秒）`
      + (note ? `<br><span style="font-size:.75rem;">${escapeHtml(note)}</span>` : "");
  };
  paint();
  _busyTimer = setInterval(paint, 1000);
}
function stopBusy() { if (_busyTimer) { clearInterval(_busyTimer); _busyTimer = null; } }

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
  // 前後の引用符・空白を除去（Windowsの「パスのコピー」で付く "…" 対策）。
  const path = $("path").value.trim().replace(/^["']|["']$/g, "").trim();
  $("path").value = path;
  const profile = $("profile").value;
  if (!path) { $("status").textContent = "動画をドロップ／選択するか、パスを入力してください。"; return; }
  // 検出オプション。内容ベース(フィラー/重複/言い直し)は文字起こしが前提。
  const rules = [];
  if ($("r_silence").checked) rules.push("silence");
  if ($("r_tempo").checked) rules.push("tempo");
  if ($("r_filler").checked) rules.push("filler");
  if ($("r_duplicate").checked) rules.push("duplicate");
  if ($("r_restate").checked) rules.push("restate");
  const contentRules = ["filler", "duplicate", "restate"].filter((r) => rules.includes(r));
  const needTranscript = contentRules.length > 0;
  const lang = $("lang").value;

  $("analyze").disabled = true;
  startBusy("解析中", needTranscript
    ? "文字起こしを使用中。初回はモデル取得で数分かかることがあります。"
    : "");
  try {
    // rules は常に送る（空＝全OFF）。lang でWhisperの言語を指定。
    const url = `/api/analyze?path=${encodeURIComponent(path)}&profile=${encodeURIComponent(profile)}`
      + `&rules=${encodeURIComponent(rules.join(","))}&transcript=${needTranscript ? "1" : "0"}`
      + `&lang=${encodeURIComponent(lang)}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "解析に失敗しました");
    STATE = {
      media: data.media,
      report: data.report,
      transcript: data.transcript || "",
      transcribed: !!data.transcribed,
      contentRules,
      candidates: data.candidates.map((c) => ({ ...c, enabled: true })),
    };
    $("video").src = `/media?path=${encodeURIComponent(path)}`;
    $("result").classList.remove("hidden");
    // 空状態のガイド（無言の空振り防止）。
    if (STATE.candidates.length === 0) {
      $("status").textContent = rules.length === 0
        ? "検出項目が選ばれていません。まず「無音」にチェックを入れて解析してください。"
        : `解析完了: ${data.media.name} — 該当するカット箇所は見つかりませんでした。`;
    } else {
      $("status").textContent = `解析完了: ${data.media.name}`;
    }
    renderCandidates(); renderMetrics(); renderWarnings(); renderTranscript();
    loadWaveform(path); // タイムライン背景に波形（装飾・非同期）
  } catch (e) {
    $("status").textContent = "エラー: " + e.message;
  } finally {
    stopBusy();
    $("analyze").disabled = false;
  }
}

async function doExport() {
  if (!STATE) return;
  $("export").disabled = true;
  $("exportout").innerHTML = `<span class="spin"></span>書き出し中…`
    + ($("render").checked ? "（実カット動画は時間がかかります）" : "");
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

// 再生位置に合わせて playhead を動かす。編集後プレビュー時は有効カットを飛ばす。
$("video").addEventListener("timeupdate", () => {
  if (!STATE) return;
  const v = $("video");
  if ($("preview").checked) {
    const t = v.currentTime;
    for (const c of STATE.candidates) {
      if (c.enabled && t >= c.start && t < c.end - 0.02) { v.currentTime = c.end; break; }
    }
  }
  $("play").style.left = pct(v.currentTime, STATE.media.duration) + "%";
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

// --- ファイル投入（アップロード）・ドラッグ&ドロップ・お試し動画 ---
async function uploadFile(file) {
  $("status").textContent = `読み込み中… ${file.name}`;
  try {
    const res = await fetch(`/api/upload?name=${encodeURIComponent(file.name)}`,
      { method: "POST", body: file });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "読み込みに失敗しました");
    $("path").value = data.path;
    $("status").textContent = `読み込み完了: ${file.name} → 「解析」を押してください`;
  } catch (e) {
    $("status").textContent = "エラー: " + e.message;
  }
}

$("pick").onclick = () => $("file").click();
$("file").addEventListener("change", (e) => { if (e.target.files[0]) uploadFile(e.target.files[0]); });

const drop = $("drop");
["dragover", "dragenter"].forEach((ev) => drop.addEventListener(ev, (e) => {
  e.preventDefault(); drop.style.borderColor = "var(--accent)";
}));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => {
  e.preventDefault(); drop.style.borderColor = "var(--border)";
}));
drop.addEventListener("drop", (e) => { if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]); });

$("sample").onclick = async () => {
  $("status").textContent = "お試し動画を作成中…";
  try {
    const res = await fetch("/api/make_sample", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "作成に失敗しました");
    $("path").value = data.path;
    $("status").textContent = "お試し動画を作成しました → 「解析」を押してください";
  } catch (e) {
    $("status").textContent = "エラー: " + e.message;
  }
};
