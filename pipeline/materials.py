"""Material check: plain code, no model.

If a listing names what the item is made of and the model's code sits in a chapter for a different
material (wood described, base-metal chapter chosen), the answer is not shown as final. Instead the
seller gets a question, and one of the options is the schedule's own catch-all line for that material
("other articles of wood"), which is where customs puts most finished goods of a material that have no
line of their own.
"""
import re

MATERIALS = {
    "wood":    (r"\b(wood|wooden|oak|pine|beech|birch|walnut|ash|maple|cherry wood|mahogany|teak|plywood|mdf|bamboo|timber|driftwood)\b", {44, 46}),
    "metal":   (r"\b(steel|iron|brass|copper|alumin(i)?um|zinc|tin|pewter|metal|wrought)\b", set(range(72, 84))),
    "plastic": (r"\b(plastic|acrylic|polypropylene|polyethylene|pvc|polycarbonate|resin|vinyl|abs)\b", {39}),
    "glass":   (r"\b(glass)\b", {70}),
    "ceramic": (r"\b(ceramic|porcelain|stoneware|earthenware|terracotta|pottery|bone china)\b", {69}),
    "textile": (r"\b(cotton|linen|wool|woollen|merino|polyester|nylon|silk|fabric|felt|knit|knitted|knitting|crochet(ed)?|woven|velvet|denim|yarn|muslin|jute|hemp)\b", set(range(50, 64))),
    "leather": (r"\b(leather|cowhide|suede)\b", {41, 42, 43}),
    "paper":   (r"\b(paper|card|cardboard|paperboard|chipboard)\b", {47, 48, 49}),
}
# Chapters that classify by what the thing is, whatever it's made of: no conflict is called there.
NEUTRAL = {33, 34, 64, 65, 66, 67, 71, 84, 85, 87, 90, 91, 92, 94, 95, 96, 97, 42}

# The schedule's residual "other articles of <material>" line, offered when the model's code conflicts.
RESIDUAL = {
    "wood":    ("4421.99.9880", "Other articles of wood"),
    "metal":   ("7326.90.8688", "Other articles of iron or steel"),
    "plastic": ("3926.90.9989", "Other articles of plastics"),
    "glass":   ("7020.00.6000", "Other articles of glass"),
    "ceramic": ("6914.90.8000", "Other ceramic articles"),
    "textile": ("6307.90.9891", "Other made up textile articles"),
    "leather": ("4205.00.8000", "Other articles of leather"),
    "paper":   ("4823.90.8600", "Other articles of paper or paperboard"),
}

def materials(text):
    t = text.lower()
    return [m for m, (pat, _) in MATERIALS.items() if re.search(pat, t)]

def conflict(text, code):
    """-> (conflict: bool, materials found). Conflict only when every named material disagrees with the code's chapter."""
    if not code: return False, []
    ms = materials(text)
    if not ms: return False, ms
    ch = int(code[:2])
    if ch in NEUTRAL: return False, ms
    material_chapter = any(ch in chs for _, chs in MATERIALS.values())
    if not material_chapter: return False, ms
    ok = any(ch in MATERIALS[m][1] for m in ms)
    return (not ok), ms
