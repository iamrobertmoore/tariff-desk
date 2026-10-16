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
    const per = Math.max(9, Math.min(ms, 1100 / (2 * n)));
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

function verdictFor(side) {
  if (!side) return { cls: "warn", lamp: "yellow", word: "NO ANSWER", text: "The untrained model didn't answer in time." };
  if (side.need) return { cls: "warn", lamp: "yellow", word: "NEEDS A FACT", text: `Asks: <b>${esc(side.need)}</b>` };
  if (side.check.valid && side.band === "strong") return { cls: "ok", lamp: "green", word: "WELL BACKED", text: `A real line in the US schedule, used in <b>${side.backing}</b> of the 12 most similar past rulings. Duty: <b>${esc(side.check.duty)}</b>.` };
  if (side.check.valid && side.band === "some") return { cls: "warn", lamp: "yellow", word: "CHECK IT", text: `A real line in the US schedule, but only <b>${side.backing}</b> of the 12 most similar past rulings used it. Check it before you ship. Duty: <b>${esc(side.check.duty)}</b>.` };
  if (side.check.valid && side.band === "none") return { cls: "bad", lamp: "red", word: "UNBACKED", text: `A real line in the US schedule, but none of the 12 most similar past rulings used it. Ask a customs broker. Duty: <b>${esc(side.check.duty)}</b>.` };
  if (side.check.valid) return { cls: "ok", lamp: "green", word: "REAL CODE", text: `A real line in the US schedule. Duty: <b>${esc(side.check.duty)}</b>.` };
  if (side.code) return { cls: "bad", lamp: "red", word: "NOT A REAL CODE", text: `<b>${side.code}</b> doesn't exist in the current US schedule. A parcel declared with it gets queried.` };
  return { cls: "bad", lamp: "red", word: "NO CODE", text: "It didn't give a code." };
}
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

$("#ask").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (busy) return;
  const text = $("#q").value.trim(); if (text.length < 3) return;
  busy = true; $("#go").disabled = true; $("#hint").className = "hint"; $("#hint").textContent = "Asking the model…";
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
  const tv = verdictFor(res.tuned), bv = verdictFor(res.base);
  const codeText = res.tuned.code ? res.tuned.code : "MORE DETAIL";
  await setText(mine.code, fmtCode(codeText), { stagger: 60 });
  mine.code.forEach((c) => c.color(tv.cls));
  setStatus(mine, tv.lamp, tv.word, res.tuned.check.valid ? `duty ${res.tuned.check.duty}` + (res.tuned.backing != null ? ` · ${res.tuned.backing} of 12 rulings` : "") : "");
  $("#hint").textContent = res.cached ? "Answered earlier, so this one came straight from the saved answer." : `Answered live in ${(res.tuned.ms / 1000).toFixed(1)}s.`;
  showResult(res, tv, bv);
  busy = false; $("#go").disabled = false;
});

async function showResult(res, tv, bv) {
  const box = $("#result"); box.hidden = false;
  if (!tunedCells) { tunedCells = flapRow($("#tunedFlaps"), CODE, [4, 7], DIGITS); baseCells = flapRow($("#baseFlaps"), CODE, [4, 7], DIGITS); }
  [...tunedCells, ...baseCells].forEach((c) => c.color(""));
  $("#tunedVerdict").innerHTML = ""; $("#baseVerdict").innerHTML = "";
  const bcode = res.base ? (res.base.code || (res.base.need ? "MORE DETAIL" : "")) : "";
  await Promise.all([
    setText(tunedCells, fmtCode(res.tuned.code || "MORE DETAIL"), { stagger: 50 }),
    setText(baseCells, fmtCode(bcode), { stagger: 50 }),
  ]);
  tunedCells.forEach((c) => c.color(tv.cls));
  // colour the untrained row from its first digit that differs from the tuned answer
  const a = (res.tuned.code || ""), b = bcode;
  let div = [...b].findIndex((ch, i) => ch !== a[i]); if (div < 0) div = b.length;
  baseCells.forEach((c, i) => c.color(i < b.length ? (bv.cls === "ok" && i < div ? "ok" : bv.cls === "ok" ? "warn" : bv.cls) : ""));
  $("#tunedVerdict").innerHTML = tv.text; $("#baseVerdict").innerHTML = bv.text;
  // the label
  const lab = $("#label"); lab.style.animation = "none"; void lab.offsetWidth; lab.style.animation = "";
  const st = $("#stamp"); st.classList.remove("on", "held");
  if (res.tuned.check.valid) {
    const path = res.tuned.check.path.filter((p) => p !== "Other");
    $("#lDesc").textContent = res.text;
    $("#lCode").textContent = res.tuned.code;
    $("#lDuty").textContent = res.tuned.check.duty;
    $("#lPath").textContent = path.join(" › ") || res.tuned.check.heading;
    st.textContent = res.tuned.band === "strong" ? "Well backed" : res.tuned.band === "some" ? "Check it" : res.tuned.band === "none" ? "Unbacked" : "Real code";
    if (res.tuned.band === "some" || res.tuned.band === "none") st.classList.add("held");
  } else {
    $("#lDesc").textContent = res.text; $("#lCode").textContent = "—"; $("#lDuty").textContent = "?";
    $("#lPath").textContent = res.tuned.need ? "Tell it: " + res.tuned.need : "No valid code";
    st.textContent = "Held"; st.classList.add("held");
  }
  if (res.precedents && res.precedents.length) {
    $("#prec").hidden = false;
    $("#precList").innerHTML = res.precedents.map(([g, c]) =>
      `<li><span>${esc(g)}</span><code class="${c === res.tuned.code ? "hit" : ""}">${esc(c)}</code></li>`).join("");
  }
  $("#reason").textContent = res.tuned.reasoning || (res.tuned.need ? "It asked instead of guessing: " + res.tuned.need : "");
  $("#copy").disabled = !res.tuned.check.valid;
  setTimeout(() => st.classList.add("on"), reduce ? 0 : 950);
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
