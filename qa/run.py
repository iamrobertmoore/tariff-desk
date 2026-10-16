"""Run realistic listings through the same path as the live page (precedents -> tuned model -> answer.decide)."""
import json, os, sys, gzip
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import precedents, answer
cfg = json.load(open(ROOT / "server/model.json")); key = os.environ.get("TINKER_API_KEY", "")
HTS = json.load(gzip.open(ROOT / "server/hts_index.json.gz", "rt")); HEAD = json.load(gzip.open(ROOT / "server/hts_headings.json.gz", "rt"))
ix = precedents.load_library(ROOT / "data/library.json.gz")
TK = "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1/completions"
CACHE = ROOT / "qa/model_cache.json"
mc = json.load(open(CACHE)) if CACHE.exists() else {}
def model(text, ctx, prefill=""):
    ck = text if not prefill else text + " ||" + prefill
    if ck in mc: return mc[ck]
    import httpx  # only needed for a listing that isn't cached yet
    p = (f"<|im_start|>system\n{cfg['system']}<|im_end|>\n<|im_start|>user\n{ctx}\n\nWhat is the HTS US Code for this product? {text}<|im_end|>\n"
         f"<|im_start|>assistant\n<think>\n\n</think>\n\n{prefill}")
    r = httpx.post(TK, headers={"Authorization": f"Bearer {key}"}, json={"model": cfg["tuned"], "prompt": p, "max_tokens": 80, "temperature": 0, "stop": ["<|im_end|>", "\n"]}, timeout=60).json()
    mc[ck] = (prefill + r["choices"][0]["text"]).strip(); json.dump(mc, open(CACHE, "w"), indent=0); return mc[ck]
def parse(t):
    import re
    m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})\.?(\d{2})", t)
    code = f"{m.group(1)}.{m.group(2)}.{m.group(3)}{m.group(4)}" if m else None
    n = re.search(r"Need\s*->\s*(.+)", t)
    return code, (n.group(1).strip() if n and not code else None)
# Usage: python3 qa/run.py qa/holdout.json   (model replies are cached in qa/model_cache.json, so no key is needed
# to re-score; a new listing needs TINKER_API_KEY). Each row: [listing, [acceptable 4-digit headings] or ["ASK"]].
rows = json.load(open(sys.argv[1] if len(sys.argv) > 1 else ROOT / "qa/listings.json"))
tally = {"best": 0, "shown": 0, "ask_ok": 0, "bad_ask": 0, "n": 0}
for text, ok in rows:
    ctx = precedents.block(ix, HTS, f"What is the HTS US Code for this product? {text}")
    code, need = parse(model(text, ctx))
    if need and answer.needs_code_anyway(text, need):   # same second call as the live server
        c2, _ = parse(model(text, ctx, prefill="HTS US Code ->"))
        if c2: code, need = c2, None
    d = answer.decide(text, code, need, ctx, HTS, HEAD)
    tally["n"] += 1
    if d["kind"] == "ask":
        good = ok == ["ASK"]; tally["ask_ok" if good else "bad_ask"] += 1
        print(f"{'OK ' if good else 'XX '} ASK  {text}  ->  {d['question']}"); continue
    hb = d["best"] and d["best"][:4] in ok
    opts = [o["code"] for o in d["options"]]
    sh = hb or any(o[:4] in ok for o in opts)
    tally["best"] += bool(hb); tally["shown"] += bool(sh)
    flag = "OK " if hb else ("~  " if sh else "XX ")
    print(f"{flag} {'CONF' if d['confident'] else 'LIST'} {text}  ->  best {d['best']} (model {code}, backing {d['backing']}{', swapped' if d['swapped'] else ''})")
    if not d["confident"]: print("        options: " + ", ".join(f"{o['code']} {(o['words'] or '')[:50]}" for o in d["options"]))
print(tally)
