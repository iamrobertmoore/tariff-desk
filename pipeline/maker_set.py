"""Set 1 (curated makers): the way a maker would describe the item in an Etsy listing.

Written by hand on Thu 15 Oct 2026, before any model was run on them. Each line keeps the facts the
ruling turned on (material, construction, use) and drops the CBP wording. The key is the ruling's own
10-digit code. Every ruling is dated Jul 2025 or later, after the training data was collected.
"""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

ITEMS = [
 ("N363812", "3406.00.0000", "Scented candle, palm and paraffin wax blend with a cotton wick, hand poured into a decorative glass jar. 10 oz."),
 ("N358156", "9405.50.4000", "Hand-painted wax candle that comes with its own steel stand, sold together as a set to light up a room. Hand poured and painted in my studio."),
 ("N363470", "7117.90.7500", "Handmade polymer clay earrings, baked clay shapes on gold-plated stainless steel posts and jump rings."),
 ("N361199", "6912.00.4500", "Cowboy boot mug! Ceramic (dolomite) cup shaped like a boot with a braided handle, pink with white stars."),
 ("N363701", "9503.00.0090", "10 inch plush teddy bear, sitting, orange, with an embroidered awareness ribbon on its tummy and a printed cape. A collectible."),
 ("N358409", "4911.91.4040", "Limited edition giclee print of my abstract painting on canvas, stretched on wooden bars and framed, signed and numbered on the back."),
 ("N363968", "4419.20.9000", "Acacia wood chopping board set: two-sided board with a removable steel strainer, two steel storage tubs with lids and a steel rack."),
 ("N363385", "4201.00.6000", "Knitted dog jumper, mostly cotton, rib-knit turtleneck, cuffs for the front legs and a short belly so they can wee."),
 ("N355302", "9404.40.1000", "Patchwork-style quilt, 100% cotton printed top, solid blue cotton back, cotton batting, stitched through in straight lines, bound edges."),
 ("N362992", "6304.93.0000", "18 x 18 inch cushion cover, 100% polyester woven, printed manatee design, envelope back. Cover only, no insert."),
 ("N362291", "6304.99.3500", "Linen cushion cover, 20 x 20 inches, 100% linen with a flange edge, envelope back, gold eyelets and a little chain with a leather tag. Insert not included."),
 ("N362270", "9615.11.4000", "Decorate-your-own claw clip kit: a plastic claw hair clip, two small clips, gem stickers and tweezers."),
 ("N362344", "6702.10.2000", "22 inch wildflower wreath, artificial plastic flowers glued onto a natural climbing-fern vine base."),
 ("N363820", "0604.90.3000", "Dried poppy seed heads for flower arranging and home decor, naturally grown and air dried, nothing added. Not for planting or eating."),
 ("N361717", "0603.90.0000", "Your wedding bouquet preserved forever: real flowers dried in silica and restored to their colours, framed behind glass in a handmade wooden frame."),
 ("N363025", "4205.00.8000", "Handmade refillable leather notebook cover, one piece of cowhide folded over, holds the notebook insert with elastic cords."),
 ("N359801", "4820.10.2060", "Hardback pocket notebook, illustrated board cover, 160 lined pages, two ribbon markers and a magnetic closure. A6."),
 ("N360900", "9405.99.4090", "Pleated silk lampshade, French drum shape, silk over a steel wire frame, fits a standard table or ceiling light."),
 ("N359791", "4420.90.8000", "Day of the Dead ofrenda shadow box, MDF wood, 8.5 inches tall with two little doors and a clip to hang a photo of a loved one."),
 ("N353934", "4823.90.6700", "Bookmark made from printed, coated chipboard, folded at the top with a small resin figure sitting on it."),
 ("N348145", "6110.30.3020", "Women's sparkly knit jumper, 81% polyamide and 19% metallic yarn, crew neck, short sleeves with ribbed cuffs and hem."),
 ("N360023", "6217.10.9510", "Adult and child clothing protector bib, 100% cotton woven, reusable, for people who need help at mealtimes."),
 ("N362754", "4823.90.6700", "Little paperboard village house for the mantelpiece, coated card with two trees and a picket fence and a small light inside. No Christmas design."),
 ("N359815", "8306.29.0000", "Galvanised iron Valentine heart and tag ornaments, painted white with pink hearts, hung with string and a wooden bead."),
 ("N362362", "9505.10.2500", "Reusable fabric Christmas crackers, set of six. Cardboard tubes covered in woven cotton with ribbon ties. Sold empty, you fill them yourself."),
 ("N363426", "9505.90.4000", "Tissue paper fringe party banner, layers of coloured tissue glued to a string, for birthdays. Single use."),
 ("N359826", "6913.90.5000", "Small ceramic character planter (dolomite) with a plastic faux succulent in it. About 3.5 inches high."),
 ("N351211", "6307.90.9891", "Oversized muslin swaddle blanket, single layer 100% cotton muslin, 48 x 49 inches, hemmed. Swaddle, nursing cover or pram shade."),
 ("N358163", "6505.00.6090", "Goldfish costume headpiece for adults, polyester knit body covering the whole head down to the shoulders, printed scales, face opening."),
 ("N362854", "8306.29.0000", "Beaded wire wall art: steel wire shaped into a gecko, owl, butterfly or dragonfly and covered in coloured glass beads, with a hanging loop."),
 ("N362694", "3907.30.0000", "Make your own resin keychain kit: two-part epoxy resin and hardener, silicone moulds, glitter, pigments, cups, sticks, droppers, jump rings and keychains."),
 ("N354748", "3926.90.9989", "Hard polycarbonate phone case with a soft foam lining, covers back, sides and corners. Fits iPhone."),
 ("N360054", "3407.00.2000", "Modelling dough flower bouquet set: dough plus plastic tools and stems to press and shape your own flowers."),
 ("N362075", "4202.92.4500", "Wheeled tote bag with a plastic sheeting outer, three handles and a zip, about 16 x 12 x 20 inches. Camping, shopping, picnics."),
]

def main():
    hts = json.load(open(ROOT / "data/hts_index.json"))
    rows = []
    for rid, code, text in ITEMS:
        assert code in hts, (rid, code)
        rows.append({"id": rid, "set": "makers", "question": f"What is the HTS US Code for this product? {text}",
                     "listing": text, "key": code, "source": f"https://rulings.cbp.gov/ruling/{rid}"})
    (ROOT / "data/key").mkdir(parents=True, exist_ok=True)
    with open(ROOT / "data/key/makers.jsonl", "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    print(len(rows), "maker items")

if __name__ == "__main__":
    main()
