"""Do the models ask instead of guessing? 60 vague listings (15 from the answer key + 45 written later),
same prompt for both (the system prompt tells every model it may answer 'Need -> <question>'),
same 12 rulings. Also counts unwanted questions on clear listings."""
import json, sys, re, httpx, concurrent.futures as cf
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline")); import precedents
cfg = json.load(open(ROOT / "repo/server/model.json")); key = open(ROOT / ".tinker-key").read().strip()
hts = json.load(open(ROOT / "data/hts_index.json")); ix = precedents.load_library()
TK = "https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1/completions"
CACHE = ROOT / "qa/vague_cache.json"; mc = json.load(open(CACHE)) if CACHE.exists() else {}
def call(model, text):
    k = model + "||" + text
    if k in mc: return mc[k]
    ctx = precedents.block(ix, hts, f"What is the HTS US Code for this product? {text}")
    p = (f"<|im_start|>system\n{cfg['system']}<|im_end|>\n<|im_start|>user\n{ctx}\n\nWhat is the HTS US Code for this product? {text}<|im_end|>\n"
         f"<|im_start|>assistant\n<think>\n\n</think>\n\n")
    r = httpx.post(TK, headers={"Authorization": f"Bearer {key}"}, json={"model": model, "prompt": p, "max_tokens": 80, "temperature": 0, "stop": ["<|im_end|>", "\n"]}, timeout=90).json()
    mc[k] = r["choices"][0]["text"].strip(); return mc[k]
asks = lambda out: out.startswith("Need") or not re.search(r"\d{4}\.\d{2}\.\d{2}", out)
adv = [json.loads(l) for l in open(ROOT / "data/key/adversarial.jsonl")]
vague = [a.get("listing") or a["question"].split("product? ")[-1] for a in adv if a.get("expect") == "ask" or a.get("kind") == "ask"]
vague += json.load(open(ROOT / "qa/vague_more.json"))
clear = [r[0] for f in ("listings", "holdout", "fresh", "users") for r in json.load(open(ROOT / f"qa/{f}.json")) if r[1] != ["ASK"]]
jobs = [(m, t) for m in ("tuned", "base") for t in vague + clear] + [("big", t) for t in vague]
with cf.ThreadPoolExecutor(8) as ex: outs = list(ex.map(lambda j: call(cfg.get(j[0], "Qwen/Qwen3.5-397B-A17B"), j[1]), jobs))
json.dump(mc, open(CACHE, "w"), indent=0)
res = dict(zip(jobs, outs))
out = {"vague_n": len(vague), "clear_n": len(clear)}
for m in ("tuned", "base", "big"):
    out[f"{m}_asked_vague"] = sum(asks(res[(m, t)]) for t in vague)
    out[f"{m}_asked_vague_new"] = sum(asks(res[(m, t)]) for t in vague[-45:])
    if m != "big": out[f"{m}_asked_clear"] = sum(asks(res[(m, t)]) for t in clear)
both = sum(asks(res[("tuned", t)]) and not asks(res[("base", t)]) for t in vague); rev = sum(asks(res[("base", t)]) and not asks(res[("tuned", t)]) for t in vague)
from math import comb
n = both + rev; p = min(1, 2 * sum(comb(n, k) for k in range(0, min(both, rev) + 1)) / 2 ** n) if n else 1
out.update(discordant_tuned=both, discordant_base=rev, mcnemar_p=p)
print(json.dumps(out, indent=1)); json.dump(out, open(ROOT / "data/vague.json", "w"), indent=1)
