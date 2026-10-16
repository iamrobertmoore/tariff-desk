"""Run one model over all three answer-key sets and write raw outputs plus scores.

    python3 evaluate.py --name base --base-model Qwen/Qwen3-8B
    python3 evaluate.py --name ft-v1 --base-model Qwen/Qwen3-8B --model-path tinker://.../sampler_weights/final

Scores are computed by score.py from the saved outputs, never typed.
"""
import argparse, asyncio, json, time
from pathlib import Path
import tk, common

ROOT = Path(__file__).resolve().parent.parent

async def main():
    a = argparse.ArgumentParser()
    a.add_argument("--name", required=True)
    a.add_argument("--base-model", default="Qwen/Qwen3-8B")
    a.add_argument("--model-path", default=None)
    a.add_argument("--sets", nargs="+", default=["makers", "unseen", "adversarial", "atlas_test"])
    a.add_argument("--rag", action="store_true", help="put the precedent block in front of each question")
    o = a.parse_args()
    client = tk.sampler(base_model=o.base_model, model_path=o.model_path)
    outdir = ROOT / "data/runs" / o.name; outdir.mkdir(parents=True, exist_ok=True)
    meta = {"name": o.name, "base_model": o.base_model, "model_path": o.model_path,
"rag": o.rag, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "usage": {}}
    for s in o.sets:
        rows = common.load(s)
        ctx = {}
        if o.rag:
            ctx = {json.loads(l)["id"]: json.loads(l)["context"] for l in open(ROOT / f"data/key/ctx_{s}.jsonl")}
        prompts = [common.messages(r["question"], context=ctx.get(r["id"])) for r in rows]
        t0 = time.time()
        outs, usage = await tk.sample_many(client, o.base_model, prompts, max_tokens=350, temperature=0.0, conc=32)
        meta["usage"][s] = dict(usage, seconds=round(time.time() - t0, 1), n=len(rows))
        with open(outdir / f"{s}.jsonl", "w") as f:
            for r, txt in zip(rows, outs):
                f.write(json.dumps({"id": r["id"], "output": txt, "parsed": common.parse(txt)}) + "\n")
        print(s, len(rows), meta["usage"][s], flush=True)
    json.dump(meta, open(outdir / "meta.json", "w"), indent=1)

asyncio.run(main())
