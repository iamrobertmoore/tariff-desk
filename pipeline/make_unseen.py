"""Set 2 (unseen): turn CBP NY rulings issued Jun-Aug 2026 into questions, keyed to the ruling's code.

The question writer sees the ruling text and is told to describe the goods only: no numbers from the
tariff, no heading names, no legal reasoning. Any question that still contains a tariff-like number,
or the word 'heading'/'subheading'/'HTS', is rejected. The key is the ruling's own code, never a model's.
"""
import json, re, asyncio, sys
from pathlib import Path
import tk

ROOT = Path(__file__).resolve().parent.parent
WRITER = "Qwen/Qwen3.5-397B-A17B"
hts = json.load(open(ROOT / "data/hts_index.json"))

INSTR = """Below is a U.S. Customs (CBP) ruling letter. Write ONE question in exactly this form:
What is the HTS US Code for <description>?

The description must describe the imported goods the way an importer would before any ruling: what the item is,
what it is made of (with percentages if given), how it is constructed, and what it is used for. One or two sentences,
at most 70 words. Do NOT include any tariff numbers, chapter, heading or subheading names, duty rates, country of
origin rules, the ruling's conclusion, or any legal reasoning. If the letter covers several items, describe only the
item that the letter classifies under the main tariff number. Reply with the question only.

RULING LETTER:
"""

def clean_text(t):
    t = re.sub(r"\s+", " ", t)
    return t[:6000]

async def main():
    rulings = json.load(open(ROOT / "data/raw/unseen_rulings.json"))
    keep = [r for r in rulings if r["code"] in hts]
    print("in current HTSUS:", len(keep), "of", len(rulings))
    c = tk.sampler(base_model=WRITER)
    prompts = [[{"role": "user", "content": INSTR + clean_text(r["text"])}] for r in keep]
    outs, usage = await tk.sample_many(c, WRITER, prompts, max_tokens=200, temperature=0.0, conc=24)
    rows, rej = [], 0
    for r, q in zip(keep, outs):
        q = q.strip().strip('"')
        bad = (not q.startswith("What is the HTS US Code for")) or re.search(r"\d{4}\.\d{2}", q) \
            or re.search(r"\b(heading|subheading|HTS(US)?\b(?! US Code)|chapter \d+)", q[30:], re.I)
        if bad:
            rej += 1; continue
        rows.append({"id": r["ruling"], "set": "unseen", "date": r["date"], "question": q, "key": r["code"],
                     "source": f"https://rulings.cbp.gov/ruling/{r['ruling']}"})
    print("kept", len(rows), "rejected", rej, "usage", usage)
    (ROOT / "data/key").mkdir(parents=True, exist_ok=True)
    with open(ROOT / "data/key/unseen.jsonl", "w") as f:
        for x in rows: f.write(json.dumps(x) + "\n")
    json.dump({"writer": WRITER, "usage": usage}, open(ROOT / "data/key/unseen_meta.json", "w"))

asyncio.run(main())
