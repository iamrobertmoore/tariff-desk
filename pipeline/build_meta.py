"""Write the site's data (server/public_meta.json, site/meta.json) and server/model.json from the scored runs.

Every number on the page comes from data/scores.json and the saved run outputs. Nothing is typed.
    python3 build_meta.py --base base-qwen3-8b --big big-qwen3.5-397b --tuned ft-v1 --tuned-path tinker://...
"""
import argparse, json, gzip, shutil
from pathlib import Path
import common

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "repo"

SHORT = {  # board labels, 16 characters max, for the maker set
 "N363812": "SCENTED CANDLE", "N358156": "CANDLE + STAND", "N363470": "CLAY EARRINGS", "N361199": "BOOT MUG",
 "N363701": "PLUSH TEDDY BEAR", "N358409": "CANVAS ART PRINT", "N363968": "CHOPPING BOARD", "N363385": "DOG JUMPER",
 "N355302": "COTTON QUILT", "N362992": "CUSHION COVER", "N362291": "LINEN CUSHION", "N362270": "CLAW CLIP KIT",
 "N362344": "WILDFLOWER WREATH"[:16], "N363820": "DRIED POPPIES", "N361717": "PRESSED BOUQUET", "N363025": "LEATHER COVER",
 "N359801": "POCKET NOTEBOOK", "N360900": "SILK LAMPSHADE", "N359791": "OFRENDA BOX", "N353934": "BOOKMARK",
 "N348145": "SPARKLY JUMPER", "N360023": "COTTON BIB", "N362754": "CARD VILLAGE", "N359815": "IRON HEARTS",
 "N362362": "FABRIC CRACKERS", "N363426": "PARTY BANNER", "N359826": "MINI PLANTER", "N351211": "MUSLIN SWADDLE",
 "N358163": "GOLDFISH HAT", "N362854": "BEADED WALL ART", "N362694": "RESIN KEYRING KIT", "N354748": "PHONE CASE",
 "N360054": "DOUGH BOUQUET", "N362075": "WHEELED TOTE",
}

EXAMPLES = [
 {"chip": "Soy candle", "text": "Hand-poured soy wax candle in a reused glass jar, 200g, lavender scent, cotton wick."},
 {"chip": "Knitted scarf", "text": "Hand-knitted scarf, 100% merino wool."},
 {"chip": "Clay earrings", "text": "Handmade polymer clay earrings on gold-plated stainless steel hooks."},
 {"chip": "Linen cushion cover", "text": "Linen cushion cover, 45 x 45 cm, envelope back, insert not included."},
 {"chip": "My curtain pole", "text": "Wooden curtain pole, 28mm oak, 2.4m long, sold with two wooden brackets and ball finials."},
 {"chip": "\"Handmade gift\"", "text": "Handmade gift for her, boho style, perfect for birthdays."},
]

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--base", required=True); a.add_argument("--big", required=True)
    a.add_argument("--tuned", required=True); a.add_argument("--tuned-path", required=True)
    a.add_argument("--plain", required=True); a.add_argument("--base-rag", required=True)
    o = a.parse_args()
    sc = json.load(open(ROOT / "data/scores.json"))
    hts = json.load(open(ROOT / "data/hts_index.json"))
    R = sc["runs"]
    u = {k: R[k]["unseen"] for k in (o.base, o.big, o.tuned)}
    n = u[o.tuned]["n"]
    pair = sc["pairs"].get(f"{o.tuned}_vs_{o.base}_unseen", {})
    def U(n): return R[n]["unseen"]
    t, b, p, br, bg = U(o.tuned), U(o.base), U(o.plain), U(o.base_rag), U(o.big)
    adv_t, adv_b = R[o.tuned]["adversarial"], R[o.base_rag]["adversarial"]
    n = t["n"]
    pair = sc["pairs"].get(f"{o.plain}_vs_{o.base}_unseen", {}).get("exact", {})
    led = json.load(open(ROOT / "data/ledger.json"))["per_code_by_run"]
    ratio = led[o.big] / led[o.tuned]
    # the live page = fine-tuned model + the plain-code answer rules (qa/metrics.py); live cost ratio measured on Tinker
    mx = ROOT / "data/metrics_extra.json"
    desk = json.load(open(mx))["unseen.desk"] if mx.exists() else {"exact": t["exact"], "valid": t["valid"]}
    lv = ROOT / "data/live.json"
    if lv.exists(): ratio = json.load(open(lv))["ratio"]
    tally = {
        "lede": f"Each answer is marked against one of {n} binding rulings US Customs issued between June and August 2026, after every model here was trained. Exact means all ten digits match the ruling.",
        "cards": [
            {"title": "Qwen3-8B, untrained", "value": b["exact"], "of": n, "sub": f"only {b['valid']} of its answers were real codes"},
            {"title": "The same 8B, fine-tuned on Tinker", "value": p["exact"], "of": n, "sub": f"{p['valid']} real codes"},
            {"title": "Tariff Desk: fine-tuned, reading similar past rulings first", "value": desk["exact"], "of": n, "win": True,
             "sub": f"{desk['valid']} real codes; asks instead of guessing on {adv_t['ask_pass']} of {adv_t['ask_n']} vague listings"},
        ],
        "foot": (f"Fine-tuning alone took the 8B from {b['exact']} to {p['exact']} exact (95% interval +{pair.get('ci95',['?','?'])[0]} to +{pair.get('ci95',['?','?'])[1]} points, paired bootstrap). "
                 f"Given the same past rulings, the untrained 8B gets {br['exact']} but never asks ({adv_b['ask_pass']} of {adv_b['ask_n']}), "
                 f"and Qwen3.5-397B gets {bg['exact']} at about {ratio:.0f} times the cost per answer. Every output and the scoring script are in the repo."),
    }
    # board rows: every maker item, in order, with the tuned model's real answer
    run = {json.loads(l)["id"]: json.loads(l) for l in open(ROOT / f"data/runs/{o.tuned}/makers.jsonl")}
    board = []
    for r in common.load("makers"):
        code = run[r["id"]]["parsed"]["code"]
        board.append({"id": r["id"], "label": SHORT.get(r["id"], r["id"])[:16], "key": r["key"], "tuned": code,
                      "tuned_valid": bool(code and code in hts)})
    meta = {"tally": tally, "board": board, "examples": EXAMPLES,
            "runs": {k: {s2: R[k][s2] for s2 in ("makers", "unseen", "adversarial") if s2 in R[k]} for k in (o.base, o.plain, o.base_rag, o.big, o.tuned)}}
    (REPO / "server").mkdir(parents=True, exist_ok=True)
    json.dump(meta, open(REPO / "server/public_meta.json", "w"), indent=1)
    json.dump(meta, open(REPO / "site/meta.json", "w"), indent=1)
    json.dump({"tuned": o.tuned_path, "base": "Qwen/Qwen3-8B", "label": f"Qwen3-8B + LoRA ({o.tuned})", "system": common.SYSTEM_RAG},
              open(REPO / "server/model.json", "w"), indent=1)
    for src, dst in [("data/hts_index.json", "server/hts_index.json.gz"), ("data/hts_headings.json", "server/hts_headings.json.gz")]:
        with open(ROOT / src, "rb") as f, gzip.open(REPO / dst, "wb") as g: shutil.copyfileobj(f, g)
    print(json.dumps(tally, indent=1))

if __name__ == "__main__":
    main()
