"""Turn the model's reply into what the seller sees. Plain code, used by the live page and by the scoring.

- Confident: at least 3 of the 12 similar past rulings used the model's code, and the code's chapter
  doesn't contradict a material the seller named. Show the code.
- Otherwise: show the best guess and ask "which of these is closest?", offering the model's code, the
  codes the past rulings used most, and the schedule's "other articles of <material>" line for any material
  named. If the model's code contradicts the material, the material's line becomes the best guess.
- If the model asked for a missing fact, pass its question on.
"""
import re, collections
import materials

def words(code, hts, headings):
    e = hts.get(code)
    if not e: return None
    segs = [x for x in e["path"] if x and x != "Other"]
    head = re.split(r"[;:]", headings.get(code[:4]) or (segs[0] if segs else ""))[0].strip()
    head = head[:70] + ("..." if len(head) > 70 else "")
    tail = segs[-1] if len(segs) > 1 else ""
    tail = re.sub(r"\s*\(\d+\)$", "", tail)
    if tail and tail.lower()[:30] not in head.lower():
        return f"{tail[:80]} · {head}"
    return head

def decide(text, code, need, context, hts, headings):
    prec = re.findall(r"-> (\d{4}\.\d{2}\.\d{4})", context.split("Schedule wording")[0])
    if need and not code:
        return {"kind": "ask", "question": need}
    backing = sum(1 for c in prec if c == code) if code else 0
    conf, mats = materials.conflict(text, code)
    best = code if (code and code in hts) else None
    swapped = False
    if conf:
        for m in mats:
            rc = materials.RESIDUAL[m][0]
            if rc in hts:
                best, swapped = rc, True
                break
    confident = bool(best) and not conf and backing >= 3
    cands = []
    for c in ([best, code] + [c for c, _ in collections.Counter(prec).most_common()] +
              [materials.RESIDUAL[m][0] for m in mats]):
        if c and c in hts and c not in cands: cands.append(c)
    cands = cands[:5]
    return {"kind": "code", "best": best, "model_code": code, "confident": confident, "backing": backing,
            "material_conflict": conf, "swapped": swapped, "materials": mats,
            "options": [] if confident else [{"code": c, "words": words(c, hts, headings), "duty": hts[c]["general"] or "see schedule"} for c in cands]}
