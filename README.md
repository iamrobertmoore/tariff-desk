<p align="center"><img src="docs/demo.gif" alt="Tariff Desk: a seller types a product, the departures board flips to its 10-digit US customs code and says how well past rulings back it" width="800"></p>

<p align="center"><img src="docs/brand/readme-banner.png" alt="Tariff Desk" width="800"></p>

<p align="center"><b>Describe what you make. Get the 10-digit US customs code your parcel needs.</b><br>
A small open model (Qwen3-8B) fine-tuned on Tinker, reading the US Customs rulings closest to your product before it answers.</p>

<p align="center"><a href="https://tariff-desk.onrender.com">Try it</a> · <a href="#results">Results</a> · <a href="data/key">Answer key</a> · <a href="pipeline">Pipeline</a></p>

I've sold wooden curtain poles on Etsy since 2020. Since the US ended de minimis in August 2025, every parcel I send to an American buyer needs a tariff code, and since 9 July 2026 Etsy wants sellers outside the US to ship with the duties paid. CBP's postal rule asks for "all applicable 10-digit HTSUS classification(s)" on every mail entry, with a compliance date of 22 October 2026. "Handmade gift" on the customs form doesn't cut it any more.

Tariff Desk is the tool I wanted: type the item the way you'd write it in a listing, get the code, the US duty from the official schedule, and a customs line you can paste into the label. If the description is too vague to classify, it asks you the one question it needs instead of guessing.

| Try this | Watch what happens |
|---|---|
| [Open the page](https://tariff-desk.onrender.com) and click **Soy candle** | The board flips to 3406.00.0000, backed by 12 of the 12 most similar past rulings, duty Free |
| Click **"Handmade gift"** | It asks what the item is and what it's made of, while the untrained model invents a code |
| Type your own product | It answers live, shows the past rulings it read, and tells you how well they back the code |

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
- **Past rulings do the heavy lifting on accuracy.** Given the same rulings, the untrained 8B gets close to the fine-tuned one on exact matches; the difference (+1.1 points, 95% interval -1.4 to +3.7) sits inside the noise. What the fine-tune adds there is behaviour: it asks instead of guessing on 13 of 15 vague listings, where the untrained model, given the same rulings, asks on 0.
- **The big model is better, and costs more.** Qwen3.5-397B with the same rulings gets 117. Per code it costs about 8 times as much at Tinker's published prices.

**How much to trust a single answer.** The page counts how many of the 12 similar rulings used the code the model picked. On the unseen set, when 3 or more did, the code matched CBP's ruling 42 times out of 80; with 1 or 2, 50 of 218; when none did, 3 of 55. So the page marks answers *well backed*, *check it* or *unbacked*, and never shows the model's own duty figure: the duty comes from the USITC schedule.

## How it works

1. **Precedent lookup (plain code).** BM25 over 86,185 past CBP rulings: 69,345 ruling subjects from CBP's CROSS database dated before June 2026, plus the public CROSS training questions. It returns the 12 closest rulings and the schedule's wording for their codes. Same block in training, evaluation and on the live page (`pipeline/precedents.py`).
2. **The model.** Qwen3-8B with a LoRA (rank 32) trained on Tinker: v1 on 19,740 examples without precedents, v2 on 5,000 examples with them, including vague listings answered with a question and listings with codes injected into the text.
3. **The guard (plain code).** Every code is checked against the current HTSUS export from USITC. A code that doesn't exist is shown as not real; the duty and the schedule wording come from the export, never from the model.

The live page runs on Render (FastAPI, `server/app.py`) and samples the fine-tuned weights through Tinker's OpenAI-compatible endpoint.

## The answer key

Written before any model ran, and kept apart from training:

- **Unseen:** 353 CBP NY rulings issued June to August 2026, each with one 10-digit code that exists in today's schedule. A large model turned each ruling into a plain description of the goods; any description containing a tariff number or the word heading was thrown out. `data/key/unseen.jsonl`
- **Makers:** 34 products written the way a seller writes a listing, each keyed to a 2025 or 2026 CBP ruling. `pipeline/maker_set.py`
- **Adversarial:** 15 vague listings ("Personalised keepsake, any name, any colour") where the right answer is a question, and 7 listings with a code or an instruction pasted into the text. `pipeline/adversarial_set.py`

Every model output is in `data/runs/`, and `pipeline/score.py` recomputes every number in this README.

## Cost

Everything, from building the answer key to both fine-tunes and all the comparisons, came to about $14.7 at Tinker's published prices (an upper bound; `data/ledger.json`). One classification on the live page costs about $0.0004.

## Limits

- An exact code on about a quarter of rulings is a start, not a broker. The page says how well each answer is backed and points high-value items to a customs broker.
- The precedent library only holds rulings whose code still exists in today's schedule, so some old but relevant rulings are missing. It got my own curtain poles wrong because the closest rulings it found were for metal and plastic curtain rods.
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
