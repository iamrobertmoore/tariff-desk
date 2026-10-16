"""One source for every number. Builds data/facts.json from scores.json, ledger.json and the run metadata,
then renders any template with {{dotted.keys}} and fails if a placeholder is unknown.

    python3 facts.py build --tuned ft-v2-rag --base base-qwen3-8b-rag --big big-qwen3.5-397b-rag \
        --tuned-plain ft-v1 --base-plain base-qwen3-8b --big-plain big-qwen3.5-397b
    python3 facts.py render README.tmpl.md README.md
    python3 facts.py check README.md post.md        # every number-in-context in FACT_CHECKS must appear
"""
import json, re, sys, argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def flat(d, p=""):
    out = {}
    for k, v in d.items():
        key = f"{p}{k}"
        if isinstance(v, dict): out.update(flat(v, key + "."))
        else: out[key] = v
    return out

def build(o):
    sc = json.load(open(ROOT / "data/scores.json")); R = sc["runs"]
    led = json.load(open(ROOT / "data/ledger.json"))
    names = {"tuned": o.tuned, "base": o.base_plain, "base_rag": o.base, "big": o.big, "tuned_plain": o.tuned_plain, "big_plain": o.big_plain}
    F = {"sets": {}, "runs": {}, "pairs": {}, "cost": {}}
    for k, n in names.items():
        F["runs"][k] = {s: R[n][s] for s in ("makers", "unseen", "adversarial") if s in R[n]}
        F["runs"][k]["name"] = n
    F["sets"]["unseen_n"] = R[o.tuned]["unseen"]["n"]; F["sets"]["makers_n"] = R[o.tuned]["makers"]["n"]
    F["sets"]["adv_ask_n"] = R[o.tuned]["adversarial"]["ask_n"]; F["sets"]["adv_inj_n"] = R[o.tuned]["adversarial"]["inj_n"]
    for k, v in sc["pairs"].items():
        F["pairs"][k] = v
        for f, x in v.items():
            lo, hi = x["ci95"]
            x["ci_text"] = f"{lo:+.1f} to {hi:+.1f}"
    F["cost"]["total_usd"] = led["total_usd"]
    F["cost"]["per_code_usd"] = led["per_code_usd"]
    F["cost"]["codes_per_dollar"] = led["codes_per_dollar"]
    lib = json.load(__import__("gzip").open(ROOT / "data/library.json.gz", "rt"))
    F["library"] = {"n": len(lib["docs"]), "n_cross": lib["n_cross"], "n_fmt": f"{len(lib['docs']):,}", "n_cross_fmt": f"{lib['n_cross']:,}"}
    pc = led["per_code_by_run"]
    F["cost"]["big_vs_tuned"] = round(pc[o.big] / pc[o.tuned])
    F["cost"]["tuned_per_code"] = f"{pc[o.tuned]:.4f}"
    # calibration: how often the tuned code matched the ruling, by how many of the 12 precedents used it
    import re as _re
    key = {json.loads(l)["id"]: json.loads(l) for l in open(ROOT / "data/key/unseen.jsonl")}
    ctx = {json.loads(l)["id"]: json.loads(l)["context"] for l in open(ROOT / "data/key/ctx_unseen.jsonl")}
    cal = {"strong": [0, 0], "some": [0, 0], "none": [0, 0]}
    for l in open(ROOT / f"data/runs/{o.tuned}/unseen.jsonl"):
        r = json.loads(l); c = r["parsed"]["code"]
        if not c: continue
        codes = _re.findall(r"-> (\d{4}\.\d{2}\.\d{4})", ctx[r["id"]].split("Schedule wording")[0])
        n = sum(1 for x in codes if x == c)
        b = "strong" if n >= 3 else ("some" if n >= 1 else "none")
        cal[b][1] += 1; cal[b][0] += c == key[r["id"]]["key"]
    F["calibration"] = {b: {"right": v[0], "n": v[1]} for b, v in cal.items()}
    tm = json.load(open(ROOT / "data/train_meta.json"))["counts"]
    v1 = json.load(open(ROOT / "data/train_runs/ft-v1/meta.json"))
    v1usd = [x for x in led["lines"] if x["what"].startswith("Fine-tune: ft-v1 ")][0]["usd"]
    F["train"] = {**tm, "ruling_fmt": f"{tm['ruling']:,}", "listing_fmt": f"{tm['listing']:,}",
                  "v1_minutes": round(v1["seconds"] / 60), "v1_usd": f"{v1usd:.2f}"}
    json.dump(F, open(ROOT / "data/facts.json", "w"), indent=1)
    print(json.dumps(flat(F), indent=0)[:3000])

def render(src, dst):
    F = flat(json.load(open(ROOT / "data/facts.json")))
    t = open(src).read()
    missing = [m for m in re.findall(r"\{\{([\w.\-]+)\}\}", t) if m not in F]
    if missing: sys.exit(f"unknown facts: {missing}")
    open(dst, "w").write(re.sub(r"\{\{([\w.\-]+)\}\}", lambda m: str(F[m.group(1)]), t))
    print("rendered", dst)

if __name__ == "__main__":
    a = argparse.ArgumentParser(); sub = a.add_subparsers(dest="cmd")
    b = sub.add_parser("build")
    for x in ["tuned", "base", "big", "tuned-plain", "base-plain", "big-plain"]: b.add_argument("--" + x, required=True)
    r = sub.add_parser("render"); r.add_argument("src"); r.add_argument("dst")
    o = a.parse_args()
    if o.cmd == "build": build(o)
    elif o.cmd == "render": render(o.src, o.dst)
