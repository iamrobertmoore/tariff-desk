"use strict";
const CHARS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-/&'?";
const DIGITS = " 0123456789."; // code drums only carry digits, like a real departures board
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = (s) => document.querySelector(s);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ---------- sound: a short click per flap, synthesised, off by default ---------- */
let audio = null, soundOn = false, lastClick = 0;
function click() {
  if (!soundOn || !audio) return;
  const now = audio.currentTime;
  if (now - lastClick < 0.012) return;
  lastClick = now;
  const len = 0.018, buf = audio.createBuffer(1, audio.sampleRate * len, audio.sampleRate), d = buf.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / d.length, 6);
  const s = audio.createBufferSource(), g = audio.createGain(), f = audio.createBiquadFilter();
  f.type = "bandpass"; f.frequency.value = 2400 + Math.random() * 900; g.gain.value = 0.18;
  s.buffer = buf; s.connect(f).connect(g).connect(audio.destination); s.start();
}
$("#sound").addEventListener("click", (e) => {
  soundOn = !soundOn;
  if (soundOn && !audio) audio = new (window.AudioContext || window.webkitAudioContext)();
  e.currentTarget.setAttribute("aria-pressed", soundOn);
  e.currentTarget.textContent = soundOn ? "Sound on" : "Sound off";
});

/* ---------- one split flap ---------- */
class Flap {
  constructor(parent, ch = " ", cls = "", set = CHARS) {
    this.set = set;
    this.el = document.createElement("span");
    this.el.className = "f " + cls;
    this.el.innerHTML = '<span class="hu"><span></span></span><span class="hl"><span></span></span><span class="fu"><span></span></span><span class="fl"><span></span></span>';
    [this.t, this.b, this.ft, this.fb] = [...this.el.children].map((x) => x.firstChild);
    this.ch = ch; this.paint(ch);
    parent.appendChild(this.el);
  }
  paint(c) { this.t.textContent = this.b.textContent = this.ft.textContent = this.fb.textContent = c; }
  async step(next, ms) {
    this.ft.textContent = this.ch; this.b.textContent = this.ch;
    this.t.textContent = next; this.fb.textContent = next;
    this.el.style.setProperty("--fs", ms + "ms");
    this.el.classList.remove("go"); void this.el.offsetWidth; this.el.classList.add("go");
    click();
    await sleep(ms * 2);
    this.b.textContent = next; this.ft.textContent = next; this.el.classList.remove("go");
    this.ch = next;
  }
  async to(target, { ms = 34, delay = 0, spins = 0 } = {}) {
    const S = this.set;
    target = (target || " ").toUpperCase();
    if (!S.includes(target)) target = S === DIGITS && /[A-Z]/.test(target) ? target : " ";
    if (reduce || !S.includes(target)) { this.ch = target; this.paint(target); return; }
    await sleep(delay);
    let i = S.indexOf(this.ch); if (i < 0) i = 0;
    const end = S.indexOf(target);
    let n = (end - i + S.length) % S.length + spins * S.length;
    if (n === 0 && spins === 0) return;
    const per = Math.max(6, Math.min(ms, (window.__flapCap || 1100) / (2 * n)));
    while (n-- > 0) { i = (i + 1) % S.length; await this.step(S[i], per); }
  }
  color(c) { this.el.classList.remove("ok", "bad", "warn"); if (c) this.el.classList.add(c); }
}

function flapRow(parent, n, dotsAt = [], set = CHARS) {
  const wrap = document.createElement("div"); wrap.className = "flaps"; parent.appendChild(wrap);
  const cells = [];
  for (let i = 0; i < n; i++) cells.push(new Flap(wrap, " ", dotsAt.includes(i) ? "dot" : "", set));
  return cells;
}
const setText = (cells, text, opt = {}) =>
  Promise.all(cells.map((c, i) => c.to(text[i] || " ", { ...opt, delay: (opt.delay || 0) + i * (opt.stagger ?? 28) })));
const fmtCode = (c) => (c ? c : "").padEnd(12, " ");
// green up to the first digit that differs from the reference, red from there on
function colourAgainst(cells, got, ref) {
  let div = [...got].findIndex((ch, i) => ch !== ref[i]); if (div < 0) div = got.length;
  cells.forEach((c, i) => c.color(i >= got.length ? "" : i < div ? "ok" : "bad"));
}

/* ---------- board rows ---------- */
const GOODS = 16, CODE = 12;
function makeRow(top = false) {
  const row = document.createElement("div"); row.className = "row" + (top ? " mine" : "");
  const goods = flapRow(row, GOODS);
  const code = flapRow(row, CODE, [4, 7], DIGITS);
  const st = document.createElement("div"); st.className = "status";
  st.innerHTML = '<span class="lamp"></span><span class="word"></span><small></small>';
  row.appendChild(st);
  return { row, goods, code, st };
}
function setStatus(r, lamp, word, note = "") {
  r.st.querySelector(".lamp").className = "lamp " + lamp;
  r.st.querySelector(".word").textContent = word;
  r.st.querySelector("small").textContent = note;
}
function short(text) {
  const t = text.toUpperCase().replace(/[^A-Z0-9 .\-/&']/g, " ").replace(/\s+/g, " ").trim();
  if (t.length <= GOODS) return t;
  const cut = t.slice(0, GOODS + 1); const sp = cut.lastIndexOf(" ");
  return (sp > 8 ? cut.slice(0, sp) : t.slice(0, GOODS)).trim();
}

const rowsEl = $("#rows");
const boardRows = [];
let meta = null, boardIdx = 0, rotating = null;

async function showBoardItem(r, item, delay = 0) {
  const ok = item.tuned === item.key, valid = item.tuned_valid;
  setStatus(r, "", "");
  await Promise.all([setText(r.goods, item.label.padEnd(GOODS), { delay }), setText(r.code, fmtCode(item.tuned), { delay: delay + 120 })]);
  colourAgainst(r.code, item.tuned || "", item.key);
  if (ok) setStatus(r, "green", "CLEARED", "matches CBP " + item.id);
  else if (valid) setStatus(r, "red", "WRONG CODE", "CBP: " + item.key);
  else if (item.tuned) setStatus(r, "red", "NOT A REAL CODE", "CBP: " + item.key);
  else setStatus(r, "yellow", "ASKING", "wanted one more fact");
}

async function initBoard() {
  for (let i = 0; i < 6; i++) { const r = makeRow(); rowsEl.appendChild(r.row); boardRows.push(r); }
  try { meta = await (await fetch("api/meta")).json(); } catch { meta = await (await fetch("meta.json")).json(); }
  renderTally(); renderChips();
  const items = meta.board;
  await Promise.all(boardRows.map((r, i) => showBoardItem(r, items[i % items.length], i * 260)));
  boardIdx = 6;
  rotating = setInterval(async () => {
    if (document.hidden || busy) return;
    const r = boardRows[boardIdx % boardRows.length];
    await showBoardItem(r, items[boardIdx % items.length]);
    boardIdx++;
  }, 4200);
}

/* ---------- tally ---------- */
function renderTally() {
  const t = meta.tally;
  $("#nLede").textContent = t.lede;
  $("#tally").innerHTML = t.cards.map((c) => `
    <div class="t ${c.win ? "win" : ""}"><div class="big">${c.value}<small>of ${c.of}</small></div>
    <p>${c.title}</p><p class="sub">${c.sub}</p></div>`).join("");
  $("#nFoot").textContent = t.foot;
}
function renderChips() {
  $("#chips").innerHTML = meta.examples.map((e, i) => `<button type="button" data-i="${i}">${e.chip}</button>`).join("");
  $("#chips").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    $("#q").value = meta.examples[+b.dataset.i].text; $("#ask").requestSubmit();
  });
}

/* ---------- classify ---------- */
let busy = false, mine = null;
let tunedCells = null, baseCells = null;

function baseVerdict(side, tunedAsked) {
  if (!side) return { cls: "warn", text: "The untrained model didn't answer in time." };
  if (side.need && !side.code) return { cls: "warn", text: `It asked: <b>${esc(side.need)}</b>` };
  if (tunedAsked && side.code) return { cls: "bad", text: `It guessed <b>${esc(side.code)}</b> for a description that doesn't say what the item is or what it's made of.` };
  if (side.check && side.check.valid) return { cls: "warn", text: `It answered <b>${esc(side.code)}</b>, a real line in the schedule.` };
  if (side.code) return { cls: "bad", text: `<b>${esc(side.code)}</b> doesn't exist in the US schedule.` };
  return { cls: "bad", text: "It didn't give a code." };
}
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

$("#ask").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (busy) return;
  const text = $("#q").value.trim(); if (text.length < 3) return;
  busy = true; $("#go").disabled = true; $("#hint").className = "hint"; $("#hint").textContent = "Reading past rulings and asking the model. This takes a few seconds.";
  if (!mine) { mine = makeRow(true); rowsEl.prepend(mine.row); }
  mine.code.forEach((c) => c.color(""));
  setStatus(mine, "yellow", "CHECKING", "");
  const goodsP = setText(mine.goods, short(text).padEnd(GOODS));
  let spinning = true;
  const spin = (async () => { while (spinning) { await Promise.all(mine.code.map((c, i) => [4, 7].includes(i) ? c.to(".") : c.to(DIGITS[1 + Math.floor(Math.random() * 10)], { ms: 30 }))); } })();
  let res;
  try {
    const r = await fetch("api/classify", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text }) });
    res = await r.json();
    if (!r.ok) throw new Error(res.detail || "Something went wrong.");
  } catch (err) {
    spinning = false; await spin; await setText(mine.code, fmtCode(""));
    setStatus(mine, "red", "NOT SENT", ""); $("#hint").className = "hint err"; $("#hint").textContent = err.message;
    busy = false; $("#go").disabled = false; return;
  }
  spinning = false; await spin; await goodsP;
  const A = res.answer;
  if (A.kind === "ask") {
    await setText(mine.code, fmtCode("MORE DETAIL"), { stagger: 60 });
    mine.code.forEach((c) => c.color("warn"));
    setStatus(mine, "yellow", "ONE QUESTION", A.question);
  } else {
    await setText(mine.code, fmtCode(A.best || ""), { stagger: 60 });
    mine.code.forEach((c) => c.color(A.confident ? "ok" : "warn"));
    setStatus(mine, A.confident ? "green" : "yellow", A.confident ? "READY" : "PICK ONE", A.confident ? `duty ${res.duty}` : "best guess, see options");
  }
  $("#hint").textContent = res.cached ? "This one was asked before, so the answer came straight from the saved copy." : `Answered live in ${(res.tuned.ms / 1000).toFixed(1)}s.`;
  showResult(res);
  busy = false; $("#go").disabled = false;
});

function fillLabel(text, code, duty, words, stamp, held) {
  $("#lDesc").textContent = text;
  $("#lCode").textContent = code || "—";
  $("#lDuty").textContent = duty || "?";
  $("#lPath").textContent = words || "";
  const st = $("#stamp"); st.classList.remove("on", "held"); st.textContent = stamp; if (held) st.classList.add("held");
  setTimeout(() => st.classList.add("on"), reduce ? 0 : 500);
  $("#copy").disabled = !code;
}

async function showResult(res) {
  const A = res.answer, box = $("#result"); box.hidden = false;
  if (!tunedCells) { tunedCells = flapRow($("#tunedFlaps"), CODE, [4, 7], DIGITS); baseCells = flapRow($("#baseFlaps"), CODE, [4, 7], DIGITS); }
  [...tunedCells, ...baseCells].forEach((c) => c.color(""));
  $("#options").hidden = true; $("#optList").innerHTML = "";
  const lab = $("#label"); lab.style.animation = "none"; void lab.offsetWidth; lab.style.animation = "";
  if (A.kind === "ask") {
    $("#aTitle").textContent = "One question first";
    $("#aSentence").innerHTML = `Your description doesn't say enough to pick a code. <b>${esc(A.question)}</b> Add that and ask again.`;
    await setText(tunedCells, fmtCode("MORE DETAIL"), { stagger: 40 }); tunedCells.forEach((c) => c.color("warn"));
    fillLabel(res.text, "", "", "Waiting for one more detail", "Not yet", true);
    $("#q").focus();
  } else if (A.confident) {
    $("#aTitle").textContent = "Your code";
    $("#aSentence").innerHTML = `<b>${A.backing}</b> of the 12 most similar US Customs rulings used this code${A.example ? `, for example ${esc(A.example)}` : ""}. General duty rate: <b>${esc(res.duty)}</b> (extra tariffs not included).`;
    await setText(tunedCells, fmtCode(A.best), { stagger: 50 }); tunedCells.forEach((c) => c.color("ok"));
    fillLabel(res.text, A.best, res.duty, res.words, "Ready", false);
  } else {
    $("#aTitle").textContent = "Best guess, but check it";
    const mats = (A.materials || []).join(" and "), mfirst = esc(A.model_code || "");
    const WHY = {
      conflict: `It first picked a code for a different material, but your description says ${mats}, so this is the schedule line for things made of that.`,
      raw: `It first picked ${mfirst}, a line for raw or unworked material, so this is the schedule's line for finished things made of ${mats}.`,
      unbacked: `No similar US Customs ruling used the code it first picked (${mfirst}), so this is the schedule's line for things made of ${mats}.`,
      species: `It first picked ${mfirst}, the line for a different kind of wood, so this is the same line for the wood you named.`,
      heading: `The schedule has a heading written for exactly this kind of item, so its line comes ahead of the model's first pick (${mfirst}).`,
      set: `This sounds like a set of different things. US Customs classifies a retail set by the item that gives it its main character, so check this code fits the whole set, not just one piece.`,
      adult: `It first picked a line for children's toys, but your description says it's for adults, so this is the toy line for everyone else.`,
      invalid: mfirst ? `The code it first picked (${mfirst}) isn't in the US schedule, so this is the closest real line.` : "This is the closest real line in the US schedule.",
    };
    const why = WHY[A.reason] || (A.swapped && A.material_conflict ? WHY.conflict : A.swapped ? WHY.unbacked
      : A.backing ? `Only ${A.backing} of the 12 most similar US Customs rulings used this code.` : "None of the 12 most similar US Customs rulings used this code.");
    $("#aSentence").innerHTML = why + (A.example ? ` A past ruling that used this code: ${esc(A.example)}.` : "");
    await setText(tunedCells, fmtCode(A.best || ""), { stagger: 50 }); tunedCells.forEach((c) => c.color("warn"));
    const first = A.options[0] || {};
    fillLabel(res.text, A.best, first.duty, first.words, "Check it", true);
    $("#optList").innerHTML = A.options.map((o, i) =>
      `<button type="button" class="opt${i === 0 ? " on" : ""}" data-i="${i}"><code>${o.code}</code><span>${esc(o.words || "")}${i === 0 ? '<span class="tag">best guess</span>' : ""}</span><span class="d">duty ${esc(o.duty)}</span></button>`).join("");
    $("#options").hidden = false;
    $("#optList").onclick = async (ev) => {
      const b = ev.target.closest(".opt"); if (!b) return;
      const o = A.options[+b.dataset.i];
      document.querySelectorAll(".opt").forEach((x) => x.classList.toggle("on", x === b));
      $("#aTitle").textContent = "Your pick";
      await setText(tunedCells, fmtCode(o.code), { stagger: 30 }); tunedCells.forEach((c) => c.color("ok"));
      fillLabel(res.text, o.code, o.duty, o.words, "Your pick", false);
      if (mine) { await setText(mine.code, fmtCode(o.code), { stagger: 30 }); mine.code.forEach((c) => c.color("ok")); setStatus(mine, "green", "READY", `duty ${o.duty}`); }
    };
  }
  // the untrained comparison, behind a fold
  const b = res.base ? (res.base.code || (res.base.need ? "MORE DETAIL" : "")) : "";
  const bv = baseVerdict(res.base, A.kind === "ask");
  setText(baseCells, fmtCode(b), { stagger: 30 }).then(() => baseCells.forEach((c, i) => c.color(i < b.length ? bv.cls : "")));
  $("#baseVerdict").innerHTML = bv.text;
  if (res.precedents && res.precedents.length) {
    $("#precList").innerHTML = res.precedents.map(([g, c]) =>
      `<li><span>${esc(g)}</span><code class="${c === A.best ? "hit" : ""}">${esc(c)}</code></li>`).join("");
  }
  box.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "nearest" });
}

$("#copy").addEventListener("click", async () => {
  const line = `${$("#lDesc").textContent} | HS ${$("#lCode").textContent} | Origin GB`;
  try { await navigator.clipboard.writeText(line); $("#copied").hidden = false; setTimeout(() => ($("#copied").hidden = true), 1800); } catch {}
});

/* ---------- clock ---------- */
function tick() {
  $("#clock").textContent = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" }).format(new Date());
}
tick(); setInterval(tick, 10000);
document.fonts.ready.then(initBoard);

/* ---------- a whole list ---------- */
(() => {
  const area = $("#bList"), go = $("#bGo"), hint = $("#bHint"), out = $("#bOut");
  let last = [];
  const csvSplit = (line) => { const r = []; let cur = "", q = false;
    for (let i = 0; i < line.length; i++) { const ch = line[i];
      if (q) { if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; } else if (ch === '"') q = false; else cur += ch; }
      else if (ch === '"') q = true; else if (ch === ",") { r.push(cur); cur = ""; } else cur += ch; }
    r.push(cur); return r.map((x) => x.trim()); };
  const parse = (txt, isCsv) => {
    const rows = [];
    txt.split(/\r?\n/).forEach((line, i) => {
      if (!line.trim()) return;
      let cells = line.includes("\t") ? line.split("\t").map((x) => x.trim()) : (isCsv ? csvSplit(line) : [line.trim()]);
      cells = cells.filter((x) => x !== "");
      if (!cells.length) return;
      if (rows.length === 0 && /^(ref|sku|id|reference|product|description|title)$/i.test(cells[0]) && cells.length > 1) return; // header row
      let ref = "", text = cells.join(", ");
      if (cells.length > 1 && cells[0].length <= 40) { ref = cells[0]; text = cells.slice(1).join(", "); }
      rows.push({ ref: ref || String(rows.length + 1), text });
    });
    return rows;
  };
  $("#bFile").addEventListener("change", async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const t = await f.text();
    const rows = parse(t, true);
    area.value = rows.map((r) => `${r.ref}\t${r.text}`).join("\n");
    hint.textContent = `${rows.length} products from ${f.name}.`;
  });
  const STATUS = { ready: "READY", check: "CHECK IT", detail: "NEEDS DETAIL", error: "TRY AGAIN" };
  const render = (rows) => {
    const n = (s) => rows.filter((r) => r.status === s).length;
    $("#bSum").innerHTML = `<span>${rows.length} checked</span><span style="color:var(--green)">${n("ready")} ready</span><span style="color:var(--yellow)">${n("check")} to check</span><span style="color:var(--red)">${n("detail") + n("error")} need more detail</span>`;
    $("#bRows").innerHTML = rows.map((r) => `<tr class="${r.status}">
      <td class="ref">${esc(r.ref)}</td><td>${esc(r.text)}</td>
      <td class="code">${esc(r.code || "–")}${r.words ? `<small>${esc(r.words)}${r.duty ? ` · duty ${esc(r.duty)}` : ""}</small>` : ""}</td>
      <td><span class="chip ${r.status}">${STATUS[r.status] || r.status}</span></td>
      <td class="why">${esc(r.note || "")}${r.example ? `<em>A past ruling with this code: ${esc(r.example)}</em>` : ""}${r.also && r.also.length && r.status !== "ready" ? `<em>Also worth a look: ${r.also.map(esc).join(", ")}</em>` : ""}</td></tr>`).join("");
    out.hidden = false;
  };
  $("#bOnly").addEventListener("change", (e) => out.classList.toggle("only", e.target.checked));
  go.addEventListener("click", async () => {
    const rows = parse(area.value, false);
    if (!rows.length) { hint.textContent = "Paste at least one product first."; area.focus(); return; }
    if (rows.length > 25) hint.textContent = `Checking the first 25 of ${rows.length}.`;
    go.disabled = true; const t0 = performance.now();
    hint.textContent = `Checking ${Math.min(rows.length, 25)} products. This takes a few seconds.`;
    try {
      const r = await fetch("api/batch", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ items: rows.slice(0, 25) }) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || "Something went wrong.");
      last = j.rows; render(last);
      hint.textContent = `Done in ${((performance.now() - t0) / 1000).toFixed(1)}s.`;
    } catch (e) { hint.textContent = e.message; }
    go.disabled = false;
  });
  $("#bDl").addEventListener("click", () => {
    const q = (x) => `"${String(x ?? "").replace(/"/g, '""')}"`;
    const head = ["ref", "description", "hts_code", "status", "us_duty_general_rate", "schedule_wording", "why", "example_ruling", "other_codes_to_consider"];
    const lines = [head.join(",")].concat(last.map((r) => [r.ref, r.text, r.code, r.status, r.duty, r.words, r.note, r.example, (r.also || []).join(" ")].map(q).join(",")));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    a.download = "tariff-desk-results.csv"; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  });
})();
