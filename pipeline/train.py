"""LoRA SFT of Qwen3-8B on Tinker. Logs loss per step, saves sampler checkpoints, records token counts.

    python3 train.py --name ft-v1 --epochs 2 --lr 3e-4 --batch 64 --rank 32
"""
import argparse, json, time, random, math
from pathlib import Path
import tinker
from tinker import types
import tk, common

ROOT = Path(__file__).resolve().parent.parent

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--name", required=True)
    a.add_argument("--base-model", default="Qwen/Qwen3-8B")
    a.add_argument("--epochs", type=float, default=2)
    a.add_argument("--lr", type=float, default=3e-4)
    a.add_argument("--batch", type=int, default=64)
    a.add_argument("--rank", type=int, default=32)
    a.add_argument("--save-every", type=int, default=150)
    a.add_argument("--data", default="data/train.jsonl")
    a.add_argument("--rag", action="store_true", help="examples already carry the precedent block; use the RAG system prompt")
    a.add_argument("--max-usd", type=float, default=None, help="hard stop: never train past this many dollars ($0.44 per million tokens)")
    o = a.parse_args()
    out = ROOT / "data/train_runs" / o.name; out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in open(ROOT / o.data)]
    datums, ntok = [], []
    for r in rows:
        if o.rag:
            ctx, q = r["q"].rsplit("\n\n", 1)
            msgs = common.messages(q, r["a"], context=ctx)
        else:
            msgs = common.messages(r["q"], r["a"])
        d, n = tk.sft_datum(o.base_model, msgs)
        datums.append(d); ntok.append(n)
    print("examples", len(datums), "tokens/epoch", sum(ntok), flush=True)
    sc = tk.service()
    tc = sc.create_lora_training_client(base_model=o.base_model, rank=o.rank)
    steps_per_epoch = len(datums) // o.batch
    total = int(steps_per_epoch * o.epochs)
    if o.max_usd:
        avg = sum(ntok) / len(ntok)
        cap = int(o.max_usd / 0.44e-6 / (avg * o.batch))
        if cap < total: print(f"budget cap: {total} -> {cap} steps", flush=True); total = cap
    order = []
    rnd = random.Random(11)
    while len(order) < total * o.batch:
        idx = list(range(len(datums))); rnd.shuffle(idx); order += idx
    log = open(out / "log.jsonl", "w")
    ckpts = []
    t0 = time.time(); trained_tokens = 0
    for step in range(total):
        lr = o.lr * (1 - step / total)  # linear decay
        batch_idx = order[step * o.batch:(step + 1) * o.batch]
        batch = [datums[i] for i in batch_idx]
        trained_tokens += sum(ntok[i] for i in batch_idx)
        fb = tc.forward_backward(batch, loss_fn="cross_entropy")
        op = tc.optim_step(types.AdamParams(learning_rate=lr, beta1=0.9, beta2=0.95, eps=1e-8))
        r = fb.result(); op.result()
        # mean NLL per target token
        tot_l = tot_w = 0.0
        for o_, d in zip(r.loss_fn_outputs, batch):
            lp = o_["logprobs"].tolist() if hasattr(o_["logprobs"], "tolist") else o_["logprobs"].data
            w = d.loss_fn_inputs["weights"].tolist() if hasattr(d.loss_fn_inputs["weights"], "tolist") else d.loss_fn_inputs["weights"].data
            tot_l += -sum(x * y for x, y in zip(lp, w)); tot_w += sum(w)
        nll = tot_l / max(tot_w, 1)
        rec = {"step": step + 1, "of": total, "nll": round(nll, 4), "lr": lr, "tokens": trained_tokens, "sec": round(time.time() - t0)}
        log.write(json.dumps(rec) + "\n"); log.flush()
        if (step + 1) % 10 == 0 or step == 0: print(rec, flush=True)
        if (step + 1) % o.save_every == 0 or step + 1 == total:
            tag = "final" if step + 1 == total else f"step{step+1:04d}"
            path = tc.save_weights_for_sampler(name=f"{o.name}-{tag}").result().path
            ckpts.append({"step": step + 1, "path": path}); print("saved", tag, path, flush=True)
            json.dump({"args": vars(o), "examples": len(datums), "tokens_per_epoch": sum(ntok), "trained_tokens": trained_tokens,
                       "checkpoints": ckpts, "seconds": round(time.time() - t0)}, open(out / "meta.json", "w"), indent=1)

if __name__ == "__main__":
    main()
