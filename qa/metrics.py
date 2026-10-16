"""Looser measures per run, for the write-up: exact 10-digit, 6-digit subheading, 4-digit heading, real codes,
same duty rate as CBP's code, and how often no code came back. 'desk' is the live page: the fine-tuned model
plus the plain-code answer rules (pipeline/answer.py). Writes data/metrics_extra.json."""
import json, gzip, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import answer
hts = json.load(gzip.open(ROOT / "server/hts_index.json.gz", "rt")); heads = json.load(gzip.open(ROOT / "server/hts_headings.json.gz", "rt"))
runs = {"base": "base-qwen3-8b", "ft": "ft-v1", "base_rag": "base-qwen3-8b-rag", "tuned": "ft-v2-lean",
        "big": "big-qwen3.5-397b-rag", "big_plain": "big-qwen3.5-397b", "desk": "ft-v2-lean"}
duty = lambda c: (hts.get(c, {}).get("general") or "").strip()
out = {}
for s in ["unseen", "makers"]:
    key = {json.loads(l)["id"]: json.loads(l) for l in open(ROOT / f"data/key/{s}.jsonl")}
    ctx = {json.loads(l)["id"]: json.loads(l)["context"] for l in open(ROOT / f"data/key/ctx_{s}.jsonl")}
    for k, r in runs.items():
        st = dict(n=0, exact=0, d6=0, d4=0, valid=0, duty=0, asked=0)
        conf = dict(n=0, exact=0, d4=0, duty=0)
        for l in open(ROOT / f"data/runs/{r}/{s}.jsonl"):
            x = json.loads(l); p = x["parsed"]; K = key[x["id"]]["key"]; st["n"] += 1; c = p["code"]; d = None
            if k == "desk":
                q = key[x["id"]].get("listing") or key[x["id"]]["question"]
                d = answer.decide(q, p["code"], p["need"], ctx[x["id"]], hts, heads)
                c = d.get("best") if d["kind"] == "code" else None
            if not c: st["asked"] += 1; continue
            st["exact"] += c == K; st["d6"] += c[:7] == K[:7]; st["d4"] += c[:4] == K[:4]
            dm = c in hts and duty(c) == duty(K)
            st["valid"] += c in hts; st["duty"] += dm
            if d and d.get("confident"):
                conf["n"] += 1; conf["exact"] += c == K; conf["d4"] += c[:4] == K[:4]; conf["duty"] += dm
        out[f"{s}.{k}"] = st
        if k == "desk": out[f"{s}.desk_conf"] = conf
        print(s, k, st)
json.dump(out, open(ROOT / "data/metrics_extra.json", "w"), indent=1)
