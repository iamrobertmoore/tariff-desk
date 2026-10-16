"""Small helpers around the Tinker SDK: chat rendering, batch sampling, SFT datums."""
import os, asyncio, re
from pathlib import Path
import tinker
from tinker import types
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
if (ROOT / ".tinker-key").exists(): os.environ.setdefault("TINKER_API_KEY", (ROOT / ".tinker-key").read_text().strip())

_tok = {}
def tokenizer(model):
    hf = {"Qwen/Qwen3-8B": "Qwen/Qwen3-8B"}.get(model, model)
    if hf not in _tok:
        _tok[hf] = AutoTokenizer.from_pretrained(hf)
    return _tok[hf]

def render(model, messages, add_generation_prompt=True):
    t = tokenizer(model)
    return t.apply_chat_template(messages, tokenize=False, add_generation_prompt=add_generation_prompt,
                                 enable_thinking=False)

def encode(model, text):
    return tokenizer(model).encode(text, add_special_tokens=False)

def decode(model, ids):
    return tokenizer(model).decode(ids, skip_special_tokens=True)

_service = None
def service():
    global _service
    if _service is None:
        _service = tinker.ServiceClient()
    return _service

def sampler(base_model=None, model_path=None):
    if model_path:
        return service().create_sampling_client(model_path=model_path)
    return service().create_sampling_client(base_model=base_model)

async def sample_many(client, model, prompts, max_tokens=400, temperature=0.0, conc=32):
    """prompts: list of message lists. Returns list of strings (assistant text)."""
    sem = asyncio.Semaphore(conc)
    stop = ["<|im_end|>"]
    usage = {"prompt": 0, "completion": 0}
    async def one(msgs):
        async with sem:
            ids = encode(model, render(model, msgs))
            for attempt in range(4):
                try:
                    res = await client.sample_async(prompt=types.ModelInput.from_ints(ids), num_samples=1,
                        sampling_params=types.SamplingParams(max_tokens=max_tokens, temperature=temperature, stop=stop))
                    out = res.sequences[0].tokens
                    usage["prompt"] += len(ids); usage["completion"] += len(out)
                    txt = decode(model, out)
                    return re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
                except Exception as e:
                    if attempt == 3: return f"__ERROR__ {e}"
                    await asyncio.sleep(2 + attempt * 3)
    outs = await asyncio.gather(*[one(p) for p in prompts])
    return outs, usage

def sft_datum(model, messages):
    """messages ends with the assistant turn; loss only on the assistant tokens."""
    prompt = render(model, messages[:-1], add_generation_prompt=True)
    full = render(model, messages, add_generation_prompt=False)
    assert full.startswith(prompt[: len(prompt) - 30]), "template mismatch"
    p_ids = encode(model, prompt)
    completion = full[len(prompt):] if full.startswith(prompt) else None
    if completion is None:
        completion = messages[-1]["content"] + "<|im_end|>\n"
    c_ids = encode(model, completion)
    toks = p_ids + c_ids
    w = [0.0] * len(p_ids) + [1.0] * len(c_ids)
    return types.Datum(model_input=types.ModelInput.from_ints(toks[:-1]),
                       loss_fn_inputs=dict(target_tokens=toks[1:], weights=w[1:])), len(toks)
