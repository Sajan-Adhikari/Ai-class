"""AI-as-a-judge: checks subtle fabrication and rates usability 1-5.
Uses ONE fixed judge model (JUDGE_MODEL) for every model being compared."""
import os
import json

from llm import chat, parse_json

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

Step 2 - Usability, 1-5, as the candidate submitting this for THIS job:
5 = submit as-is: faithful, clearly targeted to the job, professional wording
4 = minor wording tweaks only
3 = usable after small edits (one weak or off-target bullet, slightly generic wording)
2 = needs major rework (several weak bullets, generic AI-sounding phrasing, poor targeting)
1 = unusable (fabrication, wrong job, or broken output)
Any faithfulness problem caps usability at 2.

Respond with ONLY a JSON object:
{"faithful": true, "issues": ["<problem, quoting the words>"], "usability": 4, "reason": "<one sentence>"}"""


def judge(resume_text, job_description, tailored, model=None):
    """Returns {faithful, issues, usability, reason} plus metadata."""
    model = model or DEFAULT_JUDGE
    shown = {k: tailored.get(k) for k in ("summary", "bullets", "missing_skills")}
    user = (f"<resume>\n{resume_text}\n</resume>\n\n<job>\n{job_description}\n</job>\n\n"
            f"<tailored_output>\n{json.dumps(shown, indent=2)}\n</tailored_output>")
    raw, meta = chat(model, JUDGE_PROMPT, user, max_tokens=2000)
    out = {"judge_model": model, **meta}
    if meta["error"]:
        return out
    try:
        data = parse_json(raw)
        out["faithful"] = bool(data.get("faithful"))
        out["issues"] = [str(i) for i in data.get("issues", []) or []]
        out["usability"] = max(1, min(5, int(data.get("usability", 1))))
        out["reason"] = str(data.get("reason", ""))
    except Exception as e:
        out["error"] = f"Bad judge JSON: {e}"
    return out
