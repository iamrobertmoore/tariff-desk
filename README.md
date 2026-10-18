<p align="center"><img src="docs/demo.gif" alt="Tariff Desk: a seller types a product, the departures board flips to its 10-digit US customs code and says how well past rulings back it" width="800"></p>

<p align="center"><img src="docs/brand/readme-banner.png" alt="Tariff Desk" width="800"></p>

<p align="center"><b>Describe what you make. Get the 10-digit US customs code your parcel needs.</b><br>
A small open model (Qwen3-8B) fine-tuned on Tinker, reading the US Customs rulings closest to your product before it answers.</p>

<p align="center"><a href="https://tariff-desk.onrender.com">Try it</a> · <a href="#results">Results</a> · <a href="data/key">Answer key</a> · <a href="pipeline">Pipeline</a></p>

I've sold wooden curtain poles on Etsy since 2020. Since the US ended de minimis in August 2025, every parcel I send to an American buyer needs a tariff code, and since 9 July 2026 Etsy wants sellers outside the US to ship with the duties paid. Since 24 July 2026, CBP's postal entry process has asked for "all applicable 10-digit HTSUS classification(s)" on every mail entry. "Handmade gift" on the customs form doesn't cut it any more.

Tariff Desk is the tool I wanted: type the item the way you'd write it in a listing, get the code, the US duty from the official schedule, and a customs line you can paste into the label. If the description is too vague to classify, it asks you the one question it needs instead of guessing.

| Try this | Watch what happens |
|---|---|
| [Open the page](https://tariff-desk.onrender.com) and click **Soy candle** | The board flips to 3406.00.0000, backed by 12 of the 12 most similar past rulings, duty Free |
| Click **"Handmade gift"** | It asks what the item is and what it's made of, while the untrained model invents a code |
| Click **My curtain pole** | It's not sure, so it shows its best guess (other articles of wood, 4421.99.9880) and asks which code on its short list is closest |
| Paste a few rows from your spreadsheet into **Check a whole list** | Every code comes back marked ready, check it, or needs detail, with the reason and a past ruling, and downloads as a CSV |

## The problem, in numbers

- CBP processed over **1.36 billion** de minimis shipments in fiscal 2024 ([Federal Register 2026-12669](https://www.federalregister.gov/documents/2026/06/24/2026-12669/indefinite-suspension-of-the-de-minimis-exemption-for-mail-shipments-and-new-postal-informal-entry)). Those parcels now need a 10-digit code each.
- Etsy made duties-paid shipping compulsory for sellers outside the US from **9 July 2026**, and a seller who ships duties-unpaid can end up paying the refund ([Etsy Seller Handbook](https://www.etsy.com/seller-handbook/article/1355662653395)).
- The US schedule has about 20,000 ten-digit lines, and a general model guesses ones that look right. Asked about 353 recent rulings, an untrained Qwen3-8B gave a real code 5 times.

## Results

Every answer below is marked against one of **353 binding rulings US Customs issued in June, July and August 2026**, after every model here was trained and after the training data was collected. Exact means all ten digits match the ruling. Same prompt for every model; "with past rulings" means each model reads the same 12 most similar rulings from a library of 86,185.

| Model | Exact (of 353) | Right to 6 digits | Real codes | Asks when the listing is vague (of 15) |
|---|---|---|---|---|
| Qwen3-8B, untrained | 0 | 2 | 5 | 14 |
| Qwen3-8B, fine-tuned on Tinker | **30** | 51 | 252 | 15 |
| Qwen3-8B, untrained, with past rulings | 91 | 133 | 345 | 0 |
| **Tariff Desk: fine-tuned, with past rulings** | **95** | 130 | 331 | **13** |
| Qwen3.5-397B (about 50 times the parameters), with past rulings | 117 | 176 | 319 | 15 |

What I take from it:

- **Fine-tuning taught the 8B the job.** On its own it went from 0 to 30 exact codes (paired bootstrap over the 353 rulings: +8.5 points, 95% interval +5.7 to +11.6), and from 5 to 252 real codes.
- **Past rulings account for most of the accuracy.** Given the same rulings, the untrained 8B gets close to the fine-tuned one on exact matches; the difference (+1.1 points, 95% interval -1.4 to +3.7) sits inside the noise. There the fine-tune changes behaviour: every model gets the same prompt, which allows one question instead of a code, and on 60 vague listings the fine-tuned 8B asks 57 times against 3 for the untrained one (the 397B: 59). On 98 clear listings it asked 2 times.
- **The big model is better, and costs more.** Qwen3.5-397B with the same rulings gets 117. Per answer it costs about 9 times as much at Tinker's prices ($1.98 against $0.23 per 1,000).

**One answer, or one question.** The page shows a code when it's confident: at least 4 of the 12 similar rulings used it and it doesn't contradict a material the seller named. That happened 44 times on the unseen set, and 29 matched CBP's ruling. When it isn't sure, it shows its best guess and asks "which of these is closest to your item?" with up to five codes in the schedule's own words; the right code was in that list 113 times out of 309. Altogether the right code was on screen for 142 of 353.

A few plain-code rules sit on top (`pipeline/answer.py`, `pipeline/materials.py`): a wooden item never leads with a metal or raw-timber code, oak doesn't get the bamboo line, and headings whose own wording settles it (dog coats "of any material" in 4201, greeting cards, wooden picture frames, toys) win over the model. When the model asks what something is made of but the listing already says, the page asks it again for its best code. They took the lead answer from 96 to 100 exact codes on the unseen set and from 12 to 15 of 34 on the maker listings. On 26 realistic listings in `qa/` the lead answer had the right heading on 23 of 26 (the old page: 14). I fixed bugs these listings exposed, so treat that as a sanity check rather than a clean test.

## How it works

1. **Precedent lookup (plain code).** BM25 over 86,185 past CBP rulings: 69,345 ruling subjects from CBP's CROSS database dated before June 2026, plus the public CROSS training questions. It returns the 12 closest rulings and the schedule's wording for their codes. Same block in training, evaluation and on the live page (`pipeline/precedents.py`).
2. **The model.** Qwen3-8B with a LoRA (rank 32) trained on Tinker: v1 on 19,740 examples without precedents, v2 on 5,000 examples with them, including vague listings answered with a question and listings with codes injected into the text.
3. **The guard (plain code).** Every code is checked against the current HTSUS export from USITC. A code that doesn't exist is shown as not real; the duty and the schedule wording come from the export; the model only picks the code.

The live page runs on Render (FastAPI, `server/app.py`) and samples the fine-tuned weights through Tinker's OpenAI-compatible endpoint.

## The answer key

Written before any model ran, and kept apart from training:

- **Unseen:** 353 CBP NY rulings issued June to August 2026, each with one 10-digit code that exists in today's schedule. A large model turned each ruling into a plain description of the goods; any description containing a tariff number or the word heading was thrown out. `data/key/unseen.jsonl`
- **Makers:** 34 products written the way a seller writes a listing, each keyed to a 2025 or 2026 CBP ruling. `pipeline/maker_set.py`
- **Adversarial:** 15 vague listings ("Personalised keepsake, any name, any colour") where the right answer is a question, and 7 listings with a code or an instruction pasted into the text. `pipeline/adversarial_set.py`

Every model output is in `data/runs/`, and `pipeline/score.py` recomputes every number in this README.

## Cost

Everything, from building the answer key to both fine-tunes and all the comparisons, came to $14.47 on Tinker's own usage report (`data/tinker_billing.json`). The fine-tuned model costs about $0.23 per 1,000 answers on the live page.

## Limits

- An exact code on about a quarter of rulings is no substitute for a customs broker. The page says when it isn't sure; check a code before you ship anything valuable.
- The precedent library only holds rulings whose code still exists in today's schedule, so some old but relevant rulings are missing. That's why the model got my own wooden curtain poles wrong (it found rulings for metal and plastic rods); the material rules now catch it and lead with the right line.
- US only, and only the classification: no landed-cost calculation, and no Section 232 or other additional duties.

## Run it yourself

```bash
pip install -r server/requirements.txt
export TINKER_API_KEY=...
uvicorn server.app:app --port 8787
```

The pipeline (`pipeline/`) rebuilds the answer key, the training data, both fine-tunes and every score; see the docstring at the top of each script.

## Credits

Base model Qwen3-8B (Apache-2.0). Training questions from the public CROSS rulings dataset released with the ATLAS paper (arXiv:2509.18400). Rulings from U.S. Customs and Border Protection's CROSS database and the tariff schedule from the U.S. International Trade Commission (both public). Built for the DEV Hacktoberfest 2026 "Side Hustle" challenge. MIT licence.
