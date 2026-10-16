"""Embed the precedent rulings once (bge-small-en-v1.5, ONNX via fastembed). Saved for the server."""
import time, numpy as np, retrieve
from fastembed import TextEmbedding
m = TextEmbedding("BAAI/bge-small-en-v1.5")
ix, _ = retrieve.load_index()
t = time.time()
E = np.array(list(m.embed(ix.docs, batch_size=128)), dtype=np.float32)
np.save(retrieve.ROOT / "data/rulings_emb.npy", E)
print("embedded", E.shape, round(time.time() - t, 1))
