"""Cost ledger from recorded token counts and Tinker's published prices (USD per million tokens, 15 Oct 2026).

Prices: https://tinker-docs.thinkingmachines.ai/tinker/models/ (prefill, sample, train).
Prefill is charged at the uncached rate here, so these are upper bounds.
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
PRICE = {"Qwen/Qwen3-8B": (0.195, 0.60, 0.44), "Qwen/Qwen3.5-397B-A17B": (1.65, 7.50, 6.60), "Qwen/Qwen3.6-35B-A3B": (0.45, 1.335, 1.177)}

def cost(model, prompt=0, completion=0, train=0):
    p, s, t = PRICE[model]
    return (prompt * p + completion * s + train * t) / 1e6

def main(tuned_run):
    L = []
    um = json.load(open(ROOT / "data/key/unseen_meta.json"))
    L.append(("Writing the unseen-set questions", um["writer"], cost(um["writer"], um["usage"]["prompt"], um["usage"]["completion"])))
    tm = json.load(open(ROOT / "data/train_meta.json"))
    for k in ["usage_listing", "usage_ask"]:
        L.append((f"Training data: {k.split('_')[1]} examples", tm["writer"], cost(tm["writer"], tm[k]["prompt"], tm[k]["completion"])))
    for run in sorted((ROOT / "data/runs").iterdir()):
        m = json.load(open(run / "meta.json"))
        p = sum(v["prompt"] for v in m["usage"].values()); c = sum(v["completion"] for v in m["usage"].values())
        L.append((f"Evaluation: {run.name}", m["base_model"], cost(m["base_model"], p, c)))
    for tr in sorted((ROOT / "data/train_runs").iterdir()):
        logf = tr / "log.jsonl"
        if not logf.exists(): continue
        last = [json.loads(l) for l in open(logf)][-1]
        L.append((f"Fine-tune: {tr.name} ({last['tokens']:,} tokens, {last['step']} of {last['of']} steps)", "Qwen/Qwen3-8B", cost("Qwen/Qwen3-8B", train=last["tokens"])))
    xf = ROOT / "data/ledger_extra.json"
    if xf.exists():
        for x in json.load(open(xf)):
            L.append((x["what"], x["model"], cost(x["model"], train=x.get("train_tokens", 0))))
    m = json.load(open(ROOT / f"data/runs/{tuned_run}/meta.json"))["usage"]["unseen"]
    per = cost("Qwen/Qwen3-8B", m["prompt"] / m["n"], m["completion"] / m["n"])
    def per_code(run):
        mm = json.load(open(ROOT / f"data/runs/{run}/meta.json")); u = mm["usage"]["unseen"]
        return cost(mm["base_model"], u["prompt"] / u["n"], u["completion"] / u["n"])
    cmp = {r: per_code(r) for r in sys.argv[2:]}
    out = {"lines": [{"what": a, "model": b, "usd": round(c, 4)} for a, b, c in L], "total_usd": round(sum(c for *_, c in L), 2),
           "per_code_usd": per, "per_code_tokens": [round(m["prompt"] / m["n"]), round(m["completion"] / m["n"])],
           "codes_per_dollar": int(1 / per), "per_code_by_run": cmp}
    json.dump(out, open(ROOT / "data/ledger.json", "w"), indent=1)
    for x in out["lines"]: print(f"{x['usd']:8.3f}  {x['what']}")
    print(cmp); print("total", out["total_usd"], "per code", f"{per:.6f}", "codes per $", out["codes_per_dollar"])

if __name__ == "__main__":
    main(sys.argv[1])
