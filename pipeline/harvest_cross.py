"""Widen the precedent library: CBP CROSS ruling subjects with their codes, before June 2026.

Queries CROSS search once per schedule heading (its first words) plus a list of maker products.
Keeps NY rulings with one 10-digit code that exists in today's schedule, dated before 2026-06-01,
and drops every ruling used in the answer key.
"""
import json, re, time, urllib.request, urllib.parse, concurrent.futures as cf
from pathlib import Path
import common
ROOT = Path(__file__).resolve().parent.parent

MAKER = """candle soap bath bomb earrings necklace bracelet ring pendant brooch scarf hat beanie gloves mittens socks jumper sweater
cardigan dress skirt t-shirt hoodie apron tote bag backpack purse wallet pouch makeup bag mug cup plate bowl vase planter pot figurine
ornament wreath garland bunting banner card print poster sticker notebook journal bookmark calendar frame mirror lamp lampshade cushion
pillow throw blanket quilt rug doormat curtain tie-back hook bracket finial pole rod coaster placemat tea towel oven glove chopping board
spoon spatula toy doll plush teddy puzzle game kite jigsaw slime dough play kit craft kit sewing kit knitting yarn fabric ribbon lace
button bead charm keyring keychain lanyard dog collar lead harness pet bed cat toy bird feeder birdhouse plant pot hanger macrame
wall hanging tapestry embroidery patch pin badge magnet clock coat hanger basket box tin jar bottle soap dish diffuser wax melt incense
lip balm lotion cream perfume hair clip scrunchie headband comb brush bib swaddle romper bodysuit booties sleeping bag nappy""".split()

def harvest(term):
    out = []
    for page in (1, 2):
        u = "https://rulings.cbp.gov/api/search?" + urllib.parse.urlencode(dict(term=term, collection="NY", commodityGrouping="ALL", pageSize=1000, page=page, sortBy="RELEVANCE"))
        for a in range(3):
            try:
                d = json.load(urllib.request.urlopen(u, timeout=90)); break
            except Exception:
                time.sleep(2 + 3 * a); d = None
        if not d: break
        r = d.get("rulings", []); out += r
        if len(r) < 1000: break
    return out

def clean(subject):
    s = re.sub(r"\s+", " ", subject).strip()
    s = re.sub(r"^(RE:\s*)?(The\s+)?(tariff\s+)?classification(,| and| of)?( country of origin( determination)?)?( and marking)?( of| for)?\s+", "", s, flags=re.I)
    s = re.sub(r"\s+from\s+[A-Z][\w .,&'-]*\.?$", "", s)
    return s.strip(" .;")

def main():
    hts = json.load(open(ROOT / "data/hts_index.json")); heads = json.load(open(ROOT / "data/hts_headings.json"))
    terms = sorted({" ".join(re.findall(r"[A-Za-z]+", h)[:2]).lower() for h in heads.values()} | set(MAKER))
    terms = [t for t in terms if len(t) > 2]
    print(len(terms), "queries", flush=True)
    seen = {}
    with cf.ThreadPoolExecutor(8) as ex:
        for i, res in enumerate(ex.map(harvest, terms)):
            for r in res: seen[r["rulingNumber"]] = r
            if i % 100 == 0: print(i, len(seen), flush=True)
    banned = {r["id"] for s in ("makers", "unseen") for r in common.load(s)}
    keep = []
    for r in seen.values():
        ts = [t.strip() for t in (r.get("tariffs") or "").split(",") if t.strip() and not t.strip().startswith("99")]
        if len(ts) != 1 or ts[0] not in hts or r["rulingDate"] >= "2026-06-01" or r["rulingNumber"] in banned: continue
        doc = clean(r.get("subject") or "")
        if len(doc) < 4: continue
        keep.append({"ruling": r["rulingNumber"], "date": r["rulingDate"][:10], "doc": doc, "code": ts[0]})
    json.dump(keep, open(ROOT / "data/cross_precedents.json", "w"))
    print("harvested", len(seen), "kept", len(keep), "distinct codes", len({k["code"] for k in keep}))

if __name__ == "__main__":
    main()
