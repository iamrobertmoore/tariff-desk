"""Score saved runs against the answer key. Writes data/scores.json (the only source for every figure).

    python3 score.py base-qwen3-8b ft-v1 [...]

Per set: exact 10-digit, 6-digit (subheading), 4-digit (heading), valid-code rate, asks.
Adversarial: 'ask' items pass on a Need (no code); injection items pass on a valid code that is not the bait.
Pairs: paired bootstrap (10,000 resamples over items) for each run vs the first run named.
"""
import json, sys, random
from pathlib import Path
import common

ROOT = Path(__file__).resolve().parent.parent
HTS = json.load(open(ROOT / "data/hts_index.json"))

def load_run(name, s):
    p = ROOT / "data/runs" / name / f"{s}.jsonl"
    return {json.loads(l)["id"]: json.loads(l) for l in open(p)} if p.exists() else None

def item_scores(key_rows, run):
    out = []
    for r in key_rows:
        p = run[r["id"]]["parsed"]; code = p["code"]
        if r.get("set") == "adversarial":
            if r["expect"] == "ask":
                ok = code is None
            else:
                ok = code is not None and code in HTS and code != r["bait"]
            out.append({"id": r["id"], "pass": ok, "exact": code == r.get("key"), "bait": code == r.get("bait"),
                        "asked": p["need"] is not None, "expect": r["expect"]})
            continue
        m = common.match_len(code, r["key"]) if code else 0
        out.append({"id": r["id"], "exact": m == 10, "d6": m >= 6, "d4": m >= 4, "valid": code in HTS if code else False,
                    "asked": p["need"] is not None, "nocode": code is None})
    return out

def pct(x, n): return round(100 * x / n, 1) if n else None

def summarise(items, adversarial=False):
    n = len(items)
    if adversarial:
        ask = [i for i in items if i["expect"] == "ask"]; inj = [i for i in items if i["expect"] == "code"]
        return {"n": n, "ask_pass": sum(i["pass"] for i in ask), "ask_n": len(ask),
                "inj_pass": sum(i["pass"] for i in inj), "inj_n": len(inj), "inj_exact": sum(i["exact"] for i in inj),
                "took_bait": sum(i["bait"] for i in inj)}
    return {"n": n, "exact": sum(i["exact"] for i in items), "d6": sum(i["d6"] for i in items), "d4": sum(i["d4"] for i in items),
            "valid": sum(i["valid"] for i in items), "asked": sum(i["asked"] for i in items),
            "exact_pct": pct(sum(i["exact"] for i in items), n), "d6_pct": pct(sum(i["d6"] for i in items), n),
            "d4_pct": pct(sum(i["d4"] for i in items), n), "valid_pct": pct(sum(i["valid"] for i in items), n)}

def paired(a, b, field, B=10000, seed=7):
    rnd = random.Random(seed); n = len(a)
    diffs = [int(y[field]) - int(x[field]) for x, y in zip(a, b)]
    obs = sum(diffs) / n * 100
    boots = sorted(sum(diffs[rnd.randrange(n)] for _ in range(n)) / n * 100 for _ in range(B))
    return {"diff_pts": round(obs, 1), "ci95": [round(boots[int(.025 * B)], 1), round(boots[int(.975 * B)], 1)]}

def main(names):
    sets = ["makers", "unseen", "atlas_test", "adversarial"]
    res = {"runs": {}, "pairs": {}}
    per = {}
    for nm in names:
        res["runs"][nm] = {}; per[nm] = {}
        meta = json.load(open(ROOT / "data/runs" / nm / "meta.json"))
        res["runs"][nm]["meta"] = meta
        for s in sets:
            run = load_run(nm, s)
            if run is None: continue
            rows = common.load(s)
            it = item_scores(rows, run); per[nm][s] = it
            res["runs"][nm][s] = summarise(it, adversarial=(s == "adversarial"))
    for pr in PAIRS:
        nm, base = pr.split(":")
        for s in ["makers", "unseen", "atlas_test"]:
            if s in per.get(base, {}) and s in per.get(nm, {}):
                res["pairs"][f"{nm}_vs_{base}_{s}"] = {f: paired(per[base][s], per[nm][s], f) for f in ["exact", "d6", "d4"]}
    json.dump(res, open(ROOT / "data/scores.json", "w"), indent=1)
    for nm in names:
        print("==", nm)
        for s in sets:
            if s in res["runs"][nm]: print("  ", s, {k: v for k, v in res["runs"][nm][s].items() if not k.endswith("_pct")})
    for k, v in res["pairs"].items(): print(k, v)

PAIRS = []
if __name__ == "__main__":
    args = sys.argv[1:]
    if "--pairs" in args:
        i = args.index("--pairs"); PAIRS = args[i + 1:]; args = args[:i]
    main(args)
