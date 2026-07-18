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
  const { keep, removed } = computeKeep(STATE.cuts, d);
  const active = STATE.cuts.filter((c) => c.enabled).length;
  const tiles = [
    ["総尺", fmtTime(d)],
    ["残時間", fmtTime(d - removed)],
    ["削除率", `${Math.round(pct(removed, d))}%`],
    ["カット", `${active}`],
    ["残区間", `${keep.length}`],
  ];
  $("metrics").innerHTML = tiles
    .map(([k, v]) => `<div class="metric"><div class="v">${v}</div><div class="k">${k}</div></div>`)
    .join("");
}

// タイムライン再描画（各カットをドラッグ移動/端で伸縮できる赤帯として表示）。
function renderTimeline() {
  const d = STATE.media.duration || 1;
  const tl = $("timeline");
  [...tl.querySelectorAll(".cut")].forEach((n) => n.remove());
  STATE.cuts.forEach((c, i) => {
    if (!c.enabled) return;
    const el = document.createElement("div");
    el.className = "cut";
    el.style.left = pct(c.start, d) + "%";
    el.style.width = pct(Math.max(0.001, c.end - c.start), d) + "%";
    el.title = `${c.rule} ${fmtTime(c.start)}–${fmtTime(c.end)}（ドラッグ移動 / 端で伸縮 / ダブルクリックで削除）`;
    el.innerHTML = `<div class="h l" data-i="${i}" data-edge="l"></div><div class="h r" data-i="${i}" data-edge="r"></div>`;
    el.addEventListener("pointerdown", (ev) => startDrag(ev, i, ev.target.dataset.edge || "move"));
    el.addEventListener("dblclick", (ev) => { ev.stopPropagation(); STATE.cuts.splice(i, 1); refresh(); });
    tl.appendChild(el);
  });
  const ruler = $("ruler");
  ruler.innerHTML = "";
  for (let i = 0; i <= 6; i++) {
    const t = (d * i) / 6;
    const sp = document.createElement("span");
    sp.style.left = pct(t, d) + "%";
    sp.textContent = fmtTime(t);
    ruler.appendChild(sp);
  }
}

// 一覧（各カットの ON/OFF・開始/終了の微調整・削除・頭出し）。
function renderCuts() {
  const box = $("cands");
  box.innerHTML = "";
  $("candcount").textContent = `(${STATE.cuts.length} 件)`;
  STATE.cuts.forEach((c, i) => {
    const row = document.createElement("div");
    row.className = "cand";
    row.innerHTML =
      `<input type="checkbox" ${c.enabled ? "checked" : ""} data-i="${i}" title="このカットを有効/無効">` +
      `<span class="badge">${escapeHtml(c.rule)}</span>` +
      `<input class="t" type="number" step="0.05" min="0" value="${c.start.toFixed(2)}" data-i="${i}" data-f="start">` +
      `<span style="color:var(--muted)">–</span>` +
      `<input class="t" type="number" step="0.05" min="0" value="${c.end.toFixed(2)}" data-i="${i}" data-f="end">` +
      `<span class="reason">${escapeHtml(c.reason || "")}</span>` +
      `<button class="seek" data-seek="${c.start}">▶</button>` +
      `<button class="del" data-i="${i}" title="削除">✕</button>`;
    box.appendChild(row);
  });
  box.querySelectorAll("input[type=checkbox]").forEach((cb) => {
    cb.onchange = () => { STATE.cuts[+cb.dataset.i].enabled = cb.checked; renderTimeline(); renderMetrics(); };
  });
  box.querySelectorAll("input.t").forEach((inp) => {
    inp.onchange = () => {
      const c = STATE.cuts[+inp.dataset.i];
      let v = Math.max(0, Math.min(STATE.media.duration, parseFloat(inp.value) || 0));
      c[inp.dataset.f] = v;
      if (c.end <= c.start) c.end = Math.min(STATE.media.duration, c.start + 0.1);
      refresh();
    };
  });
  box.querySelectorAll("button[data-seek]").forEach((b) => { b.onclick = () => seek(+b.dataset.seek); });
  box.querySelectorAll("button.del").forEach((b) => {
    b.onclick = () => { STATE.cuts.splice(+b.dataset.i, 1); refresh(); };
  });
}

// タイムライン・一覧・メトリクスをまとめて更新。
function refresh() { renderCuts(); renderTimeline(); renderMetrics(); }

// --- タイムライン上のドラッグ編集（移動 / 端で伸縮 / 空きで新規作成） ---
let _drag = null;
function _timeAtX(clientX) {
  const r = $("timeline").getBoundingClientRect();
  return Math.max(0, Math.min(STATE.media.duration, ((clientX - r.left) / r.width) * STATE.media.duration));
}
function startDrag(ev, i, mode) {
  ev.preventDefault(); ev.stopPropagation();
  const c = STATE.cuts[i];
  _drag = { i, mode, t0: _timeAtX(ev.clientX), s0: c.start, e0: c.end };
  window.addEventListener("pointermove", onDrag);
  window.addEventListener("pointerup", endDrag, { once: true });
}
function onDrag(ev) {
  if (!_drag) return;
  const c = STATE.cuts[_drag.i];
  const dt = _timeAtX(ev.clientX) - _drag.t0;
  const D = STATE.media.duration;
  if (_drag.mode === "l") c.start = Math.max(0, Math.min(_drag.e0 - 0.05, _drag.s0 + dt));
  else if (_drag.mode === "r") c.end = Math.min(D, Math.max(_drag.s0 + 0.05, _drag.e0 + dt));
  else { const len = _drag.e0 - _drag.s0; let ns = Math.max(0, Math.min(D - len, _drag.s0 + dt)); c.start = ns; c.end = ns + len; }
  renderTimeline(); renderMetrics();
}
function endDrag() { window.removeEventListener("pointermove", onDrag); if (_drag) { renderCuts(); } _drag = null; }

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
    (r) => !STATE.cuts.some((c) => c.rule === r)
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
      // 手編集可能なカット集合（自動検出＝初期値。以後ユーザーが調整/追加/削除）。
      cuts: data.candidates.map((c) => ({
        start: c.start, end: c.end, rule: c.rule, reason: c.reason || "", enabled: true,
      })),
    };
    $("video").src = `/media?path=${encodeURIComponent(path)}`;
    $("result").classList.remove("hidden");
    // 空状態のガイド（無言の空振り防止）。
    if (STATE.cuts.length === 0) {
      $("status").textContent = rules.length === 0
        ? "検出項目が選ばれていません。まず「無音」にチェックを入れて解析するか、「＋カット追加」で手動編集できます。"
        : `解析完了: ${data.media.name} — 自動カットは0件でした。「＋カット追加」で手動編集できます。`;
    } else {
      $("status").textContent = `解析完了: ${data.media.name}`;
    }
    refresh(); renderWarnings(); renderTranscript();
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
      output_dir: $("outdir").value.trim().replace(/^["']|["']$/g, "").trim() || null,
      // 手編集後の最終カット区間を送る（有効なもののみ）。
      cuts: STATE.cuts.filter((c) => c.enabled).map((c) => ({ start: c.start, end: c.end })),
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
    for (const c of STATE.cuts) {
      if (c.enabled && t >= c.start && t < c.end - 0.02) { v.currentTime = c.end; break; }
    }
  }
  $("play").style.left = pct(v.currentTime, STATE.media.duration) + "%";
});
// タイムライン: 空き部分をクリック→シーク、ドラッグ→新規カット作成。
$("timeline").addEventListener("pointerdown", (ev) => {
  if (!STATE || ev.target.closest(".cut")) return;
  const t0 = _timeAtX(ev.clientX);
  let created = null, moved = false;
  const mv = (e) => {
    const t = _timeAtX(e.clientX);
    if (!moved && Math.abs(t - t0) < 0.08) return;
    moved = true;
    if (!created) { created = { start: t0, end: t0, rule: "manual", reason: "手動カット", enabled: true }; STATE.cuts.push(created); }
    created.start = Math.min(t0, t); created.end = Math.max(t0, t);
    renderTimeline(); renderMetrics();
  };
  const up = () => { window.removeEventListener("pointermove", mv); if (!moved) seek(t0); else renderCuts(); };
  window.addEventListener("pointermove", mv);
  window.addEventListener("pointerup", up, { once: true });
});

// 「＋ カット追加」: 再生位置に約1秒のカットを追加して手編集の起点にする。
$("addcut").onclick = () => {
  if (!STATE) return;
  const t = $("video").currentTime || 0, D = STATE.media.duration;
  const s = Math.max(0, Math.min(D - 0.2, t));
  STATE.cuts.push({ start: s, end: Math.min(D, s + 1.0), rule: "manual", reason: "手動カット", enabled: true });
  refresh();
};

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

// Googleドライブ(デスクトップ版)を検出したら「Driveに保存」ボタンを表示。
(async () => {
  try {
    const res = await fetch("/api/drive");
    const data = await res.json();
    if (res.ok && data.roots && data.roots.length) {
      const root = data.roots[0];
      const btn = $("usedrive");
      btn.style.display = "";
      btn.title = root;
      btn.onclick = () => { $("outdir").value = root + "\\VideoEditTool出力"; };
    }
  } catch (_) { /* Drive未導入なら何もしない */ }
})();

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
