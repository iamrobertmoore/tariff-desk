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

# Raw and semi-finished material headings (logs and sawn timber, unwrought metal, yarn, plain sheet...).
# A maker's finished product almost never belongs here, so when the model lands on one and fewer than 3
# similar rulings back it, it's treated like a material conflict.
def _rng(a, b): return set(range(a, b + 1))
RAW = (_rng(4401, 4412) | _rng(7001, 7008) | _rng(7106, 7112) | _rng(7201, 7229) |
       _rng(7401, 7410) | _rng(7501, 7506) | _rng(7601, 7606) | _rng(4701, 4707))

# Where the schedule's own heading wording settles it whatever the thing is made of
# (heading 4201: "dog coats and the like, of any material"; heading 9503: toys).
HINTS = [
    (r"\b(dog|dogs|puppy|cat|pet)s?\b.*\b(jumper|sweater|coat|jacket|hoodie|raincoat|jersey)s?\b|\b(jumper|sweater|coat|jacket|hoodie|raincoat)s?\b.*\b(for (your |a |the )?(dog|dogs|puppy|pet))\b",
     ["4201.00.6000"]),
    (r"\b(dog|dogs|puppy|cat|pet)s?\b.*\b(collar|lead|leash|harness|muzzle)s?\b|\b(collar|lead|leash|harness|muzzle)s?\b.*\b(dog|puppy|pet)s?\b",
     ["4201.00.3000"]),
    (r"^(\S+\s+){0,5}toys?\b(?!\s+(storage|box|boxes|bin|bins|chest|basket|bag|organi[sz]er|shelf|hammock))", ["9503.00.0073", "9503.00.0071"]),
    # 4909: "printed cards bearing personal greetings, messages or announcements ... with or without envelopes"
    (r"\b(greeting|greetings|birthday|christmas|xmas|wedding|anniversary|thank you|sympathy|valentine'?s?|mother'?s day|father'?s day|congratulations|new baby)\s+cards?\b",
     ["4909.00.4000"]),
    # 4414: "wooden frames for paintings, photographs, mirrors or similar objects"
    (r"\b(wood|wooden|oak|pine|beech|birch|ash|walnut|maple|driftwood|timber)\b.*\b(picture|photo|photograph|mirror|print)\s+frames?\b|\b(picture|photo|photograph|mirror)\s+frames?\b.*\b(wood|wooden|oak|pine|beech|birch|ash|walnut|maple)\b",
     ["4414.90.0000"]),
]
SPECIES = r"\b(oak|pine|beech|birch|ash|maple|walnut|cherry|elm|sycamore|larch|spruce|fir|alder|poplar|chestnut|hazel|olive ?wood)\b"

TROPICAL = r"\b(acacia|teak|mango ?wood|mango|sapele|iroko|mahogany|meranti|sheesham|rosewood|ebony|padauk|wenge|zebrano|bubinga|balsa|rubberwood|rubber wood|suar|tamarind|ipe)\b"

def _species(text, code, hts):
    """The model picked the bamboo, tropical-wood or other-wood line and the seller's own words say otherwise
    (oak isn't tropical, acacia is, neither is bamboo): move to the matching line in the same heading."""
    if not code or code not in hts: return code
    P = lambda c: " ".join(hts[c]["path"]).lower()
    t = text.lower(); path = P(code)
    is_bam, is_trop = "bamboo" in t, bool(re.search(TROPICAL, t))
    has_bam, has_trop = "of bamboo" in path, "of tropical wood" in path
    want = None
    if has_bam and not is_bam: want = "tropical" if is_trop else "other"
    elif has_trop and not is_trop and re.search(SPECIES, t): want = "other"
    elif is_trop and not has_trop and code[:2] == "44":
        if any("of tropical wood" in P(c) for c in hts if c[:4] == code[:4]): want = "tropical"
    if not want: return code
    same = [c for c in sorted(hts) if c[:4] == code[:4] and not hts[c].get("implied")]
    if want == "tropical": same = [c for c in same if "of tropical wood" in P(c)]
    else: same = [c for c in same if "of bamboo" not in P(c) and "of tropical wood" not in P(c)]
    leaf = hts[code]["path"][-1]
    for c in same:
        if hts[c]["path"][-1] == leaf: return c
    return same[-1] if same else code

# "Metal" covers several chapters; the catch-all line depends on which metal the seller named.
METAL_LINES = [(r"\b(copper|brass|bronze)\b", "7419.80.5050"), (r"\balumin(i)?um\b", "7616.99.5190"),
               (r"\bzinc\b", "7907.00.6000"), (r"\b(pewter|tin)\b", "8007.00.5000")]

def residual(text, m):
    if m == "metal":
        for pat, c in METAL_LINES:
            if re.search(pat, text.lower()): return c
    return materials.RESIDUAL[m][0]

def _material_line(text, mats, hts):
    """The schedule's "other articles of <material>" line for the first named material."""
    for m in mats:
        if residual(text, m) in hts: return residual(text, m)
    return None

def _chapter_line(text, chapter, hts):
    import retrieve
    sched = retrieve.schedule_index(hts)
    for i, _ in sched.search(text, k=80):
        c = sched.codes[i]
        if c[:2] == chapter and int(c[:4]) not in RAW: return c
    return None

PRECIOUS = r"\b(silver|sterling|gold|platinum|vermeil|gold[- ]filled|gold[- ]plated)\b"
ABOUT_MATERIAL = r"\b(material|materials|composition|made of|fib(er|re)s?|alloy|content|fabric)\b"

def needs_code_anyway(text, need):
    """The model asked what the thing is made of, but the seller already said ("sterling silver",
    "concrete"). Then the question is no help, and the page asks the model again for its best code."""
    if not need or not re.search(ABOUT_MATERIAL, need.lower()): return False
    return bool(materials.materials(text) or re.search(PRECIOUS, text.lower()))

def decide(text, code, need, context, hts, headings):
    prec = re.findall(r"-> (\d{4}\.\d{2}\.\d{4})", context.split("Schedule wording")[0])
    if need and not code:
        return {"kind": "ask", "question": need}
    backing = sum(1 for c in prec if c == code) if code else 0
    conf, mats = materials.conflict(text, code)
    raw = bool(code) and int(code[:4]) in RAW and backing < 3
    best = code if (code and code in hts) else None
    swapped, hinted, reason = False, False, None
    fixed = _species(text, best, hts) if best else best
    if fixed != best: best, swapped, reason = fixed, True, "species"
    in_material = bool(code) and any(int(code[:2]) in materials.MATERIALS[m][1] for m in mats)
    # The model's code contradicts a named material, sits on a raw-material line, or no similar ruling
    # backs it and it isn't even in the named material's chapters: lead with the best line in the
    # material's own chapters (falling back to "other articles of <material>").
    if mats and ((conf and backing < 3) or raw or (backing == 0 and not in_material)):
        alt = _material_line(text, mats, hts)
        if alt and alt != best:
            best, swapped = alt, True
            reason = "invalid" if not (code and code in hts) else ("conflict" if conf else ("raw" if raw else "unbacked"))
    if not best and mats:
        alt = _material_line(text, mats, hts)
        if alt: best, swapped, reason = alt, True, "invalid"
    hint_alts = []
    for pat, codes in HINTS:
        if codes[0].startswith("9503") and code and (code[:2] == "95" or backing >= 3): continue
        if re.search(pat, text.lower()) and not (best and best[:4] == codes[0][:4]):
            hint_alts = [c for c in codes if c in hts]
            if hint_alts: best, hinted, reason = hint_alts[0], True, "heading"
            break
    confident = bool(best) and best == code and not conf and not raw and backing >= 3
    counts = collections.Counter(prec)
    keep_ch = {c[:2] for c in (best, code) if c} | {f"{ch:02d}" for m in mats for ch in materials.MATERIALS[m][1]} \
              | {c[:2] for c in hint_alts}
    extra = _chapter_line(text, best[:2], hts) if best else None
    cands = []
    for c in ([best, code] + hint_alts + [residual(text, m) for m in mats] + [extra] +
              [c for c, _ in counts.most_common()]):
        if not c or c not in hts or c in cands: continue
        if c not in (best, code) and c[:2] not in keep_ch and counts[c] < 2: continue   # no pliers for a chopping board
        if int(c[:4]) in RAW and c != code: continue
        if mats and c != code and materials.conflict(text, c)[0]: continue   # a wooden item gets no plastic or metal options
        cands.append(c)
    cands = cands[:5]
    if not best and cands:   # the model's code isn't real and no material was named: lead with what the rulings used most
        best, swapped, reason = cands[0], True, "invalid"
    return {"kind": "code", "reason": reason, "best": best, "model_code": code, "confident": confident, "backing": backing,
            "material_conflict": conf, "swapped": swapped, "hinted": hinted, "raw": raw, "materials": mats,
            "options": [] if confident else [{"code": c, "words": words(c, hts, headings), "duty": hts[c]["general"] or "see schedule"} for c in cands]}
