"""Shared helpers: paths, resume loading, and one chat call to any OpenRouter model."""
import functools
import json
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_resume():
    with open(os.path.join(ROOT, "data", "resume_v1.txt"), encoding="utf-8") as f:
        return f.read()


def prompt_blocks(resume_text, job_description):
    return f"<resume>\n{resume_text}\n</resume>\n\n<job>\n{job_description}\n</job>"


# Any OpenAI-compatible API works. Pick one with LLM_PROVIDER in .env.
PROVIDERS = {  # name: (base URL, env var holding the key)
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
}
PROVIDER = os.getenv("LLM_PROVIDER", "openrouter").lower()


@functools.cache
def _client():
    if PROVIDER not in PROVIDERS:
        raise SystemExit(f"Unknown LLM_PROVIDER '{PROVIDER}'. Use one of: {', '.join(PROVIDERS)}")
    base_url, key_var = PROVIDERS[PROVIDER]
    if not os.getenv(key_var):
        raise SystemExit(f"Set {key_var} in .env (LLM_PROVIDER={PROVIDER}).")
    # The SDK retries rate limits, timeouts and 5xx with backoff; auth/bad-request errors fail fast.
    return OpenAI(base_url=base_url, api_key=os.environ[key_var], max_retries=6)


def chat(model, system, user, temperature=0.0, max_tokens=4000, **extra):
    """Returns (text, meta). meta = latency_s, input_tokens, output_tokens, error.
    extra = additional API parameters, e.g. reasoning_effort="low"."""
    start = time.perf_counter()
    try:
        resp = _client().chat.completions.create(
            model=model, temperature=temperature, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            **extra,
        )
    except Exception as e:
        return "", {"latency_s": None, "input_tokens": 0, "output_tokens": 0,
                    "error": f"API error: {e}"}
    usage = resp.usage
    return resp.choices[0].message.content or "", {
        "latency_s": time.perf_counter() - start,
        "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "error": None}


def parse_json(text):
    """Pull the first {...} object out of a model reply."""
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


def ask_json(model, system, user, parse, error_label="Bad JSON", **kw):
    """chat() + parse_json() + parse(data) -> dict of fields.
    Returns (meta, fields); a bad reply sets meta["error"] instead (not retried)."""
    raw, meta = chat(model, system, user, **kw)
    meta["raw"] = raw
    if meta["error"]:
        return meta, {}
    try:
        return meta, parse(parse_json(raw))
    except Exception as e:
        meta["error"] = f"{error_label}: {e}"
        return meta, {}
