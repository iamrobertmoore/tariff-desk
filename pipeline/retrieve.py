"""Precedent lookup: BM25 over the CBP rulings in the training split (questions only, codes attached).

Deterministic and cheap. For any description it returns the most similar past rulings and their codes,
plus the schedule's own wording for each candidate code. The model reads these as evidence; the final
answer is still checked against the schedule by plain code.
"""
import json, re, math
from pathlib import Path
import numpy as np
from scipy import sparse

ROOT = Path(__file__).resolve().parent.parent
STOP = set("the a an of for and or in on with to is are be by as at from this that what code hts us product which used it its into made".split())
TOK = re.compile(r"[a-z0-9]+")

def stem(t):
    for suf in ("ies", "es", "s"):
        if t.endswith(suf) and len(t) > len(suf) + 3:
            return t[: -len(suf)] + ("y" if suf == "ies" else "")
    return t

def toks(s):
    return [stem(t) for t in TOK.findall(s.lower()) if t not in STOP and len(t) > 1]

def strip_q(q):
    q = re.sub(r"^What is the HTS US Code for (this product\??)?", "", q.strip(), flags=re.I)
    return q.strip().rstrip("?")

class Index:
    def __init__(self, docs, codes, k1=1.4, b=0.75):
        self.docs, self.codes = docs, codes
        vocab = {}
        rows, cols, vals = [], [], []
        lens = []
        for i, d in enumerate(docs):
            tf = {}
            for t in toks(d): tf[t] = tf.get(t, 0) + 1
            lens.append(sum(tf.values()))
            for t, c in tf.items():
                j = vocab.setdefault(t, len(vocab)); rows.append(i); cols.append(j); vals.append(c)
        self.vocab = vocab
        tf = sparse.csr_matrix((vals, (rows, cols)), shape=(len(docs), len(vocab)), dtype=np.float32)
        N = len(docs); df = np.bincount(cols, minlength=len(vocab))
        self.idf = np.log(1 + (N - df + 0.5) / (df + 0.5)).astype(np.float32)
        lens = np.array(lens, dtype=np.float32); avg = lens.mean()
        tf = tf.tocoo()
        denom = tf.data + k1 * (1 - b + b * lens[tf.row] / avg)
        w = tf.data * (k1 + 1) / denom * self.idf[tf.col]
        self.W = sparse.csr_matrix((w, (tf.row, tf.col)), shape=tf.shape).T.tocsr()  # vocab x docs

    def search(self, text, k=8, exclude=None):
        q = [self.vocab[t] for t in set(toks(text)) if t in self.vocab]
        if not q: return []
        s = np.asarray(self.W[q].sum(axis=0)).ravel()
        if exclude is not None: s[exclude] = -1
        top = np.argpartition(-s, min(k * 3, len(s) - 1))[: k * 3]
        top = top[np.argsort(-s[top])]
        out, seen = [], set()
        for i in top:
            if s[i] <= 0: break
            key = (self.docs[i][:80], self.codes[i])
            if key in seen: continue
            seen.add(key); out.append((int(i), float(s[i])))
            if len(out) == k: break
        return out

def load_index():
    rows = json.load(open(ROOT / "data/atlas_train_valid.json"))
    test_q = {json.loads(l)["question"] for l in open(ROOT / "data/key/atlas_test.jsonl")}
    rows = [r for r in rows if r["question"] not in test_q]
    return Index([strip_q(r["question"]) for r in rows], [r["key"] for r in rows]), rows

_sched = None
def schedule_index(hts):
    global _sched
    if _sched is None:
        codes = [c for c, e in hts.items() if not e.get("implied")]
        _sched = Index([" ".join(x for x in hts[c]["path"] if x != "Other") for c in codes], codes, b=0.3)
    return _sched

_emb = {"E": None, "m": None}
def dense_search(index, text, k=8, exclude=None):
    import numpy as np
    if _emb["E"] is None:
        from fastembed import TextEmbedding
        _emb["E"] = np.load(ROOT / "data/rulings_emb.npy"); _emb["m"] = TextEmbedding("BAAI/bge-small-en-v1.5")
    q = np.array(list(_emb["m"].embed([text])))[0]
    s = _emb["E"] @ q
    if exclude is not None: s[exclude] = -9
    top = np.argsort(-s)[: k * 3]
    out, seen = [], set()
    for i in top:
        key = (index.docs[i][:80], index.codes[i])
        if key in seen: continue
        seen.add(key); out.append((int(i), float(s[i])))
        if len(out) == k: break
    return out

def embed_queries(texts):
    """Batch-embed many queries at once (for building training contexts)."""
    import numpy as np
    from fastembed import TextEmbedding
    if _emb["m"] is None: _emb["m"] = TextEmbedding("BAAI/bge-small-en-v1.5")
    return np.array(list(_emb["m"].embed(texts, batch_size=128)), dtype=np.float32)

def context(index, hts, text, k=8, exclude=None, qvec=None):
    """The evidence block placed in front of the question: the closest past rulings by meaning,
    then the schedule lines for their codes plus the best lexical matches in the schedule itself."""
    import numpy as np
    if qvec is not None:
        if _emb["E"] is None: _emb["E"] = np.load(ROOT / "data/rulings_emb.npy")
        s = _emb["E"] @ qvec
        if exclude is not None: s[exclude] = -9
        top = np.argsort(-s)[: k * 3]; hits, seen = [], set()
        for i in top:
            key = (index.docs[i][:80], index.codes[i])
            if key in seen: continue
            seen.add(key); hits.append((int(i), float(s[i])))
            if len(hits) == k: break
    else:
        hits = dense_search(index, strip_q(text), k=k, exclude=exclude)
    lines = ["Similar past CBP rulings (description -> code):"]
    cands = []
    for i, _ in hits:
        d = index.docs[i]
        d = d if len(d) < 220 else d[:217] + "..."
        lines.append(f"- {d} -> {index.codes[i]}")
        if index.codes[i] not in cands: cands.append(index.codes[i])
    sched = schedule_index(hts)
    for i, _ in sched.search(strip_q(text), k=4):
        if sched.codes[i] not in cands: cands.append(sched.codes[i])
    lines.append("Schedule lines that may apply:")
    for c in cands[:10]:
        e = hts.get(c)
        if e:
            p = [x for x in e["path"] if x != "Other"]
            lines.append(f"- {c}: " + " > ".join(p)[-200:])
    return "\n".join(lines)

if __name__ == "__main__":
    import time
    t = time.time(); ix, _ = load_index(); print("built", len(ix.docs), round(time.time() - t, 1), "s")
    hts = json.load(open(ROOT / "data/hts_index.json"))
    print(context(ix, hts, "Hand-poured soy wax candle in a glass jar"))
