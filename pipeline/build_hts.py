"""Index the current HTSUS (USITC export) by 10-digit code: full description path and general duty rate.

The duty rate shown to users always comes from here, never from the model.
"""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
rows = json.load(open(ROOT / "data/raw/hts.json"))
stack = []  # (indent, description, htsno, general)
index = {}
for r in rows:
    ind = int(r.get("indent") or 0)
    desc = re.sub(r"\s+", " ", (r.get("description") or "")).strip().rstrip(":")
    no = (r.get("htsno") or "").strip()
    gen = (r.get("general") or "").strip()
    while stack and stack[-1][0] >= ind:
        stack.pop()
    stack.append((ind, desc, no, gen))
    if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}\.\d{2}", no):
        code = no[:10] + no[11:]  # 1234.56.7890
        rate = gen or next((g for (_, _, n, g) in reversed(stack[:-1]) if g), "")
        index[code] = {"path": [d for (_, d, _, _) in stack if d], "general": rate}
    elif re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", no):
        # 8-digit lines with no statistical suffix are valid at 10 digits as NNNN.NN.NN00
        index.setdefault(no + "00", {"path": [d for (_, d, _, _) in stack if d], "general": gen, "implied": True})
heads = {}
for r in rows:
    no = (r.get("htsno") or "").strip()
    if re.fullmatch(r"\d{4}", no):
        heads[no] = re.sub(r"\s+", " ", r.get("description") or "").strip()
json.dump(index, open(ROOT / "data/hts_index.json", "w"))
json.dump(heads, open(ROOT / "data/hts_headings.json", "w"))
print(len(index), "codes;", len(heads), "headings;", index.get("3406.00.0000"))
