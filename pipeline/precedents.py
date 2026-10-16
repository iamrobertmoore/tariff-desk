"""The precedent block, v2: BM25 over ~86k past CBP rulings (CROSS subjects before June 2026 plus the
public CROSS training questions), and the schedule's wording for each candidate code.

Pure numpy/scipy, so the live server can run it. Used identically in training, evaluation and the product.
"""
import json, re
from pathlib import Path
import retrieve

ROOT = Path(__file__).resolve().parent.parent
K = 12

def build(atlas_rows=None):
    P = json.load(open(ROOT / "data/cross_precedents.json"))
    ix, rows = retrieve.load_index()
    docs = [p["doc"] for p in P] + ix.docs
    codes = [p["code"] for p in P] + ix.codes
    return retrieve.Index(docs, codes), len(P)

def jacc(a, b):
    A, B = set(retrieve.toks(a)), set(retrieve.toks(b))
    return len(A & B) / max(1, len(A | B))

def block(index, hts, text, exclude=None, self_code=None):
    """exclude: doc indices never to show. self_code: when training, also drop near-copies of the
    example itself (same code and mostly the same words), so the model can't just copy its own answer."""
    q = retrieve.strip_q(text)
    hits = index.search(q, k=K + 8, exclude=exclude)
    shown = []
    for i, _ in hits:
        if self_code and index.codes[i] == self_code and jacc(index.docs[i], q) > 0.6: continue
        shown.append(i)
        if len(shown) == K: break
    lines = ["Similar past CBP rulings (goods -> code):"]
    cands = []
    for i in shown:
        d = index.docs[i]; d = d if len(d) < 160 else d[:157] + "..."
        lines.append(f"- {d} -> {index.codes[i]}")
        if index.codes[i] not in cands: cands.append(index.codes[i])
    sched = retrieve.schedule_index(hts)
    for i, _ in sched.search(q, k=3):
        if sched.codes[i] not in cands: cands.append(sched.codes[i])
    lines.append("Schedule wording for those codes:")
    for c in cands[:12]:
        e = hts.get(c)
        if e:
            p = [x for x in e["path"] if x != "Other"] or e["path"]
            lines.append(f"- {c}: " + " > ".join(p)[-170:])
    return "\n".join(lines)

def export_library(path=ROOT / "data/library.json.gz"):
    """Freeze the exact precedent library (docs, codes, order) for the live server."""
    import gzip
    index, n_cross = build()
    with gzip.open(path, "wt") as f:
        json.dump({"docs": index.docs, "codes": index.codes, "n_cross": n_cross}, f)
    return path

def load_library(path=ROOT / "data/library.json.gz"):
    import gzip
    lib = json.load(gzip.open(path, "rt"))
    return retrieve.Index(lib["docs"], lib["codes"])
