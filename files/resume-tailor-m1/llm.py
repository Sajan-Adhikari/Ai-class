"""Shared helper: one chat call to any OpenRouter model, with timing and token counts."""
import json
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def chat(model, system, user, temperature=0.0, max_tokens=40000, retries=6):
    """Returns (text, meta). meta = latency_s, input_tokens, output_tokens, error."""
    client = OpenAI(base_url="https://openrouter.ai/api/v1",
                    api_key=os.environ["OPENROUTER_API_KEY"])
    last_err = None
    for attempt in range(retries):  # retry only API / rate-limit errors
        try:
            start = time.perf_counter()
            resp = client.chat.completions.create(
                model=model, temperature=temperature, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
            )
            meta = {"latency_s": time.perf_counter() - start,
                    "input_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
                    "output_tokens": getattr(resp.usage, "completion_tokens", 0) or 0,
                    "error": None}
            return resp.choices[0].message.content or "", meta
        except Exception as e:
            last_err = e
            time.sleep(2 ** attempt + 1)
    return "", {"latency_s": None, "input_tokens": 0, "output_tokens": 0,
                "error": f"API error: {last_err}"}


def parse_json(text):
    """Pull the first {...} object out of a model reply."""
    return json.loads(text[text.find("{"): text.rfind("}") + 1])
