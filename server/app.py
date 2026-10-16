"""Tariff Desk: the live product.

One endpoint does the real thing: POST /api/classify sends the seller's description to the fine-tuned
Qwen3-8B (a LoRA trained on Tinker) and, for comparison, to the same model untrained. Deterministic code
then checks every answer against the current US tariff schedule and reads the duty rate from it. The
model never supplies the duty, and a code that doesn't exist is shown as not a real code.
"""
import gzip, json, os, re, time, asyncio
from collections import defaultdict, deque
from pathlib import Path
import sys
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "site"
HTS = json.load(gzip.open(HERE / "hts_index.json.gz", "rt"))
HEADINGS = json.load(gzip.open(HERE / "hts_headings.json.gz", "rt"))
CONFIG = json.load(open(HERE / "model.json"))
sys.path.insert(0, str(HERE.parent / "pipeline"))
import precedents  # the same precedent block used in training and evaluation
import answer      # what the seller sees: a code, a pick-one list, or a question (plain code)
LIBRARY = precedents.load_library(HERE.parent / "data/library.json.gz")
TINKER = "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1/completions"
KEY = os.environ.get("TINKER_API_KEY", "")

SYSTEM = CONFIG["system"]
CODE_RE = re.compile(r"HTS US Code\s*->\s*(\d{4})\.?(\d{2})\.?(\d{2})\.?(\d{2})")
ANY_RE = re.compile(r"\b(\d{4})\.(\d{2})\.(\d{2})\.?(\d{2})\b")

def prompt(text, context, prefill=""):
    q = f"What is the HTS US Code for this product? {text}"
    return (f"<|im_start|>system\n{SYSTEM}<|im_end|>\n<|im_start|>user\n{context}\n\n{q}<|im_end|>\n"
            f"<|im_start|>assistant\n<think>\n\n</think>\n\n{prefill}")

def parse(t):
    m = CODE_RE.search(t) or ANY_RE.search(t)
    code = f"{m.group(1)}.{m.group(2)}.{m.group(3)}{m.group(4)}" if m else None
    need = None
    n = re.search(r"Need\s*->\s*(.+)", t)
    if n and not code: need = n.group(1).strip()
    r = re.search(r"Reasoning\s*->\s*(.+)", t, re.S)
    return code, need, (r.group(1).strip() if r else None)

def check(code):
    """The guard: is this a real 10-digit line in the current schedule, and what does the schedule say?"""
    if not code: return {"valid": False}
    e = HTS.get(code)
    if not e:
        head = HEADINGS.get(code[:4])
        return {"valid": False, "heading_exists": head is not None, "heading": head}
    return {"valid": True, "path": e["path"], "duty": e["general"] or "see schedule",
            "chapter": code[:2], "heading": HEADINGS.get(code[:4])}

async def ask(client, model, text, context, prefill=""):
    t0 = time.time()
    # The reply starts with "HTS US Code -> ..." or "Need -> ...", and the page only uses that first line, so
    # stop at the first newline instead of generating the reasoning: same answer, about a third of the wait.
    r = await client.post(TINKER, headers={"Authorization": f"Bearer {KEY}"}, json={
        "model": model, "prompt": prompt(text, context, prefill), "max_tokens": 80, "temperature": 0, "stop": ["<|im_end|>", "\n"]}, timeout=45)
    r.raise_for_status()
    out = (prefill + r.json()["choices"][0]["text"]).strip()
    code, need, reasoning = parse(out)
    return {"code": code, "need": need, "reasoning": reasoning, "check": check(code), "ms": int((time.time() - t0) * 1000)}

app = FastAPI(title="Tariff Desk")

def finalize(out):
    t = out["tuned"]
    ctx = precedents.block(LIBRARY, HTS, f"What is the HTS US Code for this product? {out['text']}")
    a = answer.decide(out["text"], t.get("code"), t.get("need"), ctx, HTS, HEADINGS)
    out["answer"] = a
    if a.get("best"):
        out["duty"] = HTS[a["best"]]["general"] or "see schedule"
        out["words"] = answer.words(a["best"], HTS, HEADINGS)
    return out

# Answers are deterministic (temperature 0), so a repeat of the same description is served from cache.
# The examples on the page are pre-computed into cache.json, so the first click always works and costs nothing.
CACHE_FILE = HERE / "cache.json"
CACHE = json.load(open(CACHE_FILE)) if CACHE_FILE.exists() else {}
def ckey(t): return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()
TOTAL_CAP = int(os.environ.get("TOTAL_CAP", "4000"))  # model calls since start: a hard ceiling on spend
spent = {"calls": 0}
hits = defaultdict(deque)
LIMIT, WINDOW = 20, 3600
day = {"date": "", "n": 0}
DAILY_CAP = int(os.environ.get("DAILY_CAP", "600"))

@app.post("/api/classify")
async def classify(req: Request):
    body = await req.json()
    text = re.sub(r"\s+", " ", str(body.get("text", ""))).strip()
    if len(text) < 3: raise HTTPException(400, "Describe the product in a few words.")
    if len(text) > 600: raise HTTPException(400, "Keep it under 600 characters, like a listing summary.")
    k = ckey(text)
    if k in CACHE:
        return finalize(dict(CACHE[k], cached=True))
    ip = req.headers.get("x-forwarded-for", req.client.host if req.client else "?").split(",")[0]
    q = hits[ip]; now = time.time()
    while q and now - q[0] > WINDOW: q.popleft()
    if len(q) >= LIMIT: raise HTTPException(429, "That's 20 in an hour from you. Try again a bit later.")
    today = time.strftime("%Y-%m-%d")
    if day["date"] != today: day.update(date=today, n=0)
    if day["n"] >= DAILY_CAP or spent["calls"] >= TOTAL_CAP:
        raise HTTPException(503, "The free classifications for today are used up. Try one of the examples, they're always on.")
    spent["calls"] += 1
    q.append(now); day["n"] += 1
    context = precedents.block(LIBRARY, HTS, f"What is the HTS US Code for this product? {text}")
    async with httpx.AsyncClient() as c:
        tuned, base = await asyncio.gather(ask(c, CONFIG["tuned"], text, context), ask(c, CONFIG["base"], text, context), return_exceptions=True)
    if isinstance(tuned, Exception): raise HTTPException(502, "The model didn't answer. Try again in a moment.")
    if isinstance(base, Exception): base = None
    # It asked what the thing is made of, but the seller already said: ask again, starting its reply with the
    # code line, so it gives its best code and the page shows a pick-one list instead of a pointless question.
    if tuned.get("need") and answer.needs_code_anyway(text, tuned["need"]):
        async with httpx.AsyncClient() as c:
            try:
                again = await ask(c, CONFIG["tuned"], text, context, prefill="HTS US Code ->")
                if again.get("code"): tuned = dict(again, asked_first=tuned["need"])
            except Exception:
                pass
    all_prec = [l[2:].rsplit(" -> ", 1) for l in context.split("\n") if l.startswith("- ") and " -> " in l]
    prec = all_prec[:5]
    # How many of the 12 similar past rulings used the same code. Measured on the unseen set:
    # 3 or more -> matched CBP's ruling about half the time; none -> almost never. Shown to the seller.
    if not isinstance(tuned, Exception) and tuned.get("code"):
        n = sum(1 for _, c in all_prec if c == tuned["code"])
        tuned["backing"] = n
        tuned["band"] = "strong" if n >= 3 else ("some" if n >= 1 else "none")
    out = {"text": text, "tuned": tuned, "base": base, "precedents": prec,
           "model": {"tuned": CONFIG["label"], "base": CONFIG["base"]}}
    if len(CACHE) < 5000: CACHE[k] = out
    return finalize(dict(out))

# ---------- a whole list at once (asked for by a seller with ~180 listings) ----------
BATCH_MAX, BATCH_LIMIT = 25, 4          # rows per list, lists per IP per hour
bhits = defaultdict(deque)
NOTES = {
    "conflict": "The model first picked a code for a different material; this is the line for the material named.",
    "raw": "The model first picked a raw-material line; this is the line for finished goods of that material.",
    "unbacked": "No similar ruling used the model's first pick; this is the catch-all line for the material named.",
    "species": "The model first picked the line for a different kind of wood; this is the same line for the wood named.",
    "heading": "The schedule has a heading written for this kind of item, so its line comes ahead of the model's first pick.",
    "adult": "The model first picked a children's toy line, but the description says it's for adults.",
    "set": "A set of different things: US Customs classifies a retail set by the item that gives it its main character.",
    "invalid": "The model's first pick isn't a real code; this is the closest real line.",
}

def row_result(ref, text, out):
    a = out["answer"]
    if a["kind"] == "ask":
        return {"ref": ref, "text": text, "status": "detail", "code": "", "words": "", "duty": "",
                "note": "Needs more detail: " + a["question"], "example": ""}
    note = NOTES.get(a.get("reason") or "", "")
    if a.get("confident"): status, note = "ready", note or f"{a['backing']} of the 12 most similar rulings used this code."
    else: status = "check"; note = note or (f"Only {a['backing']} of the 12 most similar rulings used this code." if a.get("backing") else "No similar ruling used this code.")
    opts = [o["code"] for o in a.get("options", [])[1:4]]
    return {"ref": ref, "text": text, "status": status, "code": a.get("best") or "", "words": out.get("words") or "",
            "duty": out.get("duty") or "", "note": note, "example": a.get("example") or "", "also": opts}

async def tuned_only(c, text):
    """One row of a list: the fine-tuned model only (no comparison call), same precedents, same rules."""
    k = ckey(text)
    if k in CACHE: return finalize(dict(CACHE[k], cached=True))
    context = precedents.block(LIBRARY, HTS, f"What is the HTS US Code for this product? {text}")
    tuned = await ask(c, CONFIG["tuned"], text, context)
    if tuned.get("need") and answer.needs_code_anyway(text, tuned["need"]):
        again = await ask(c, CONFIG["tuned"], text, context, prefill="HTS US Code ->")
        if again.get("code"): tuned = dict(again, asked_first=tuned["need"])
    all_prec = [l[2:].rsplit(" -> ", 1) for l in context.split("\n") if l.startswith("- ") and " -> " in l]
    if tuned.get("code"): tuned["backing"] = sum(1 for _, x in all_prec if x == tuned["code"])
    out = {"text": text, "tuned": tuned, "base": None, "precedents": all_prec[:5], "model": {"tuned": CONFIG["label"], "base": CONFIG["base"]}}
    return finalize(dict(out))

@app.post("/api/batch")
async def batch(req: Request):
    body = await req.json()
    rows = []
    for i, r in enumerate(body.get("items", [])[:BATCH_MAX]):
        text = re.sub(r"\s+", " ", str(r.get("text", ""))).strip()[:600]
        if len(text) >= 3: rows.append((str(r.get("ref") or i + 1)[:40], text))
    if not rows: raise HTTPException(400, "Paste at least one product description.")
    ip = req.headers.get("x-forwarded-for", req.client.host if req.client else "?").split(",")[0]
    q = bhits[ip]; now = time.time()
    while q and now - q[0] > WINDOW: q.popleft()
    if len(q) >= BATCH_LIMIT: raise HTTPException(429, "That's 4 lists in an hour from you. Try again a bit later.")
    new = sum(1 for _, t in rows if ckey(t) not in CACHE)
    today = time.strftime("%Y-%m-%d")
    if day["date"] != today: day.update(date=today, n=0)
    if day["n"] + new > DAILY_CAP or spent["calls"] + new > TOTAL_CAP:
        raise HTTPException(503, "The free classifications for today are used up. Try again tomorrow.")
    q.append(now); day["n"] += new; spent["calls"] += new
    sem = asyncio.Semaphore(5)
    async with httpx.AsyncClient() as c:
        async def one(ref, text):
            async with sem:
                try: return row_result(ref, text, await tuned_only(c, text))
                except Exception:
                    return {"ref": ref, "text": text, "status": "error", "code": "", "words": "", "duty": "", "note": "The model didn't answer; try this one again.", "example": ""}
        results = await asyncio.gather(*(one(r, t) for r, t in rows))
    return {"rows": results}

@app.get("/api/meta")
def meta():
    return JSONResponse(json.load(open(HERE / "public_meta.json")))

@app.get("/healthz")
def health(): return {"ok": True}

app.mount("/", StaticFiles(directory=SITE, html=True), name="site")
