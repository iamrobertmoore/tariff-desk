"""v2 training set: every example gets the same precedent block the live product shows.

For an example made from a public CROSS training question, that question (and any identical copy) is
excluded from its own precedents, and near-copies with the same code are dropped, so the model learns
to weigh neighbours rather than copy its own answer. Also writes data/key/ctx_<set>.jsonl for the
answer-key items (no exclusions needed: their rulings are not in the library).
"""
import json
from pathlib import Path
import precedents, retrieve, common

ROOT = Path(__file__).resolve().parent.parent

def main():
    index, n_cross = precedents.build()
    hts = json.load(open(ROOT / "data/hts_index.json"))
    by_doc, by_ans = {}, {}
    _, rows = retrieve.load_index()
    for j, r in enumerate(rows):
        i = n_cross + j
        by_doc.setdefault(index.docs[i], []).append(i)
        by_ans.setdefault(r["answer"], []).append(i)
    train = [json.loads(l) for l in open(ROOT / "data/train.jsonl")]
    out = []
    for k, d in enumerate(train):
        src = set(by_ans.get(d["a"], []))
        if d["kind"] == "ruling": src |= set(by_doc.get(retrieve.strip_q(d["q"]), []))
        for s in list(src): src |= set(by_doc.get(index.docs[s], []))
        m = common.CODE_RE.search(d["a"]); code = f"{m.group(1)}.{m.group(2)}.{m.group(3)}{m.group(4)}" if m else None
        ctx = precedents.block(index, hts, d["q"], exclude=sorted(src) or None, self_code=code)
        out.append({"kind": d["kind"], "q": ctx + "\n\n" + d["q"], "a": d["a"]})
        if k % 4000 == 0: print(k, flush=True)
    with open(ROOT / "data/train_rag.jsonl", "w") as f:
        for d in out: f.write(json.dumps(d) + "\n")
    for s in ["makers", "unseen", "adversarial", "atlas_test"]:
        with open(ROOT / f"data/key/ctx_{s}.jsonl", "w") as f:
            for r in common.load(s):
                f.write(json.dumps({"id": r["id"], "context": precedents.block(index, hts, r["question"])}) + "\n")
    print("done", len(out))

if __name__ == "__main__":
    main()
