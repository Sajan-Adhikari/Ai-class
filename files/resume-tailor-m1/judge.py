"""AI-as-a-judge: checks subtle fabrication and decides if the output is usable (yes/no).
Uses ONE fixed judge model (JUDGE_MODEL) for every model being compared."""
import json
import os

from llm import ask_json, prompt_blocks

DEFAULT_JUDGE = os.getenv("JUDGE_MODEL", "anthropic/claude-haiku-5.5")

JUDGE_PROMPT = """You are a strict reviewer checking a tailored resume against the candidate's real resume.

You get: the real resume as ID-tagged facts, a job posting, and a tailored output whose bullets
cite the fact IDs they are based on.

Step 1 - Faithfulness. For the summary and every bullet, compare it with the facts (especially the
cited ones). Flag any of these:
- a tool, technology, number, metric, year count, title, team size or domain not in the facts
- inflated strength or scope (e.g. "contributed to" -> "led", "helped" -> "owned")
- an academic project presented as professional or production work
- a skill that only appears in the skills list (K facts) presented as work experience
- a claim that the cited facts do not support
"faithful" is true only if there are NO such problems.

Step 2 - Usable. As the candidate applying for THIS job, would you submit this as-is or after
small edits (fixing a word or two, or dropping one weak bullet)?
"usable" is true only if it is faithful, clearly targeted to this job, and professionally worded.
It is false if it needs major rework: several weak or off-target bullets, generic AI-sounding
phrasing, or a broken output. Any faithfulness problem makes "usable" false.
Judge the OUTPUT, not the candidate: a weak fit for the job (too few years, missing required
skills) does not make the output unusable, because the output must not invent experience.
"missing_skills" is a private note to the candidate, not part of the submitted resume; do not
count its presence against usability.

Respond with ONLY a JSON object:
{"faithful": true, "issues": ["<problem, quoting the words>"], "usable": true, "reason": "<one sentence>"}"""


def _yes(value):
    """Models sometimes answer "true"/"yes" as strings."""
    return value is True or str(value).strip().lower() in ("true", "yes")


def _parse(data):
    faithful = _yes(data.get("faithful"))
    return {
        "faithful": faithful,
        "issues": [str(i) for i in data.get("issues") or []],
        "usable": faithful and _yes(data.get("usable")),
        "reason": str(data.get("reason", "")),
    }


def judge(resume_text, job_description, tailored, model=None):
    """Returns {faithful, issues, usable, reason} plus metadata."""
    model = model or DEFAULT_JUDGE
    shown = {k: tailored.get(k) for k in ("summary", "bullets", "missing_skills")}
    user = (prompt_blocks(resume_text, job_description)
            + f"\n\n<tailored_output>\n{json.dumps(shown, indent=2)}\n</tailored_output>")
    # Default max_tokens leaves room for reasoning judges (e.g. gpt-oss) to think before answering.
    meta, fields = ask_json(model, JUDGE_PROMPT, user, _parse, error_label="Bad judge JSON")
    meta.pop("raw")
    return {"judge_model": model, **meta, **fields}
