"""Pre-compute the page's example answers into server/cache.json (live model, called once each).

    python3 precompute_cache.py ["extra description" ...]
"""
import json, re, urllib.request, sys
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent / "repo"
meta = json.load(open(REPO / "server/public_meta.json"))
def ckey(t): return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()
path = REPO / "server/cache.json"
cache = json.load(open(path)) if path.exists() else {}
for e in meta["examples"] + [{"text": t} for t in sys.argv[1:]]:
    k = ckey(e["text"])
    if k in cache: continue
    req = urllib.request.Request("http://localhost:8787/api/classify", data=json.dumps({"text": e["text"]}).encode(),
                                 headers={"content-type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=120)); r.pop("cached", None)
    cache[k] = r
    t = r["tuned"]; b = r["base"] or {}
    print(f"{e['text'][:50]:52s} tuned {t['code'] or 'ASK: ' + str(t['need'])[:50]} valid={t['check']['valid']} | base {b.get('code')} valid={b.get('check', {}).get('valid')}")
json.dump(cache, open(path, "w"), indent=1)
print(len(cache), "cached")
