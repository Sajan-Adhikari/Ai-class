# Resume Tailor

Given a job description and my resume, this tool writes a tailored professional summary and resume bullets using only my real experience, and flags the skills the job asks for that my resume doesn't support.

## Install

bash
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env


Edit .env:

LLM_PROVIDER=groq                       # groq (free tier) or openrouter
GROQ_API_KEY=your_key_here              # or OPENROUTER_API_KEY for openrouter
TAILOR_MODEL=openai/gpt-oss-20b         # model being evaluated (default)
JUDGE_MODEL=openai/gpt-oss-120b         # fixed AI judge
TAILOR_REASONING_EFFORT=low             # reasoning models only; saves tokens

Model IDs: https://console.groq.com/docs/models (Groq) or https://openrouter.ai/models (OpenRouter).
Free-tier limits: https://console.groq.com/settings/limits. Limits are per model, so tailoring and
judging with two different models spreads the load.

## Core function

tailor.py -> tailor(resume_text, job_description, model=None) sends my resume facts (data/resume_v1.txt) and one job description to an LLM and returns:

json
{"status": "ok", "summary": "...",
 "bullets": [{"text": "...", "source": ["N4"]}],
 "missing_skills": ["Kubernetes"]}


Every bullet cites the resume fact IDs it is based on. The model is a setting (`model=` or `TAILOR_MODEL`), never hard-coded.

Try it on one job:
bash
python tailor.py my_job.txt


## Run the eval (one command)

bash
python eval.py --model openai/gpt-oss-20b --sleep 10


Switch models with --model only. Quick test first: python eval.py --model <id> --limit 5.
For the final comparison add --runs 3 (on a free tier, spread runs over several days).

| Option | Meaning |
|---|---|
| --model| model to evaluate (default TAILOR_MODEL) |
| --judge-model | AI judge model (default JUDGE_MODEL); keep it the same for every model you compare |
| --no-judge | code checks only (no judge calls) |
| --runs | repeat the full eval N times (default 1) |
| --sleep | seconds between calls; free tiers need 3-15 to stay under per-minute limits |
| --limit / --only T01,H04 | run a subset |

It prints pass rate (overall, typical, hard), faithfulness, tailor/reject accuracy, fact coverage, missing-skill recall, keyword gain vs. the untailored resume, % judged usable, error rate and latency (mean and range across runs), plus the examples that failed. Per-example scores (.csv) and full outputs (.jsonl) go to results/; one line per eval is appended to results/summary.csv.

## Check the AI judge against my own scores

1. Read some outputs in a results/..._run1.jsonl file.
2. Fill eval/human_scores.csv (my_faithful yes/no, my_usable yes/no).
3. python judge_check.py --results results/<file>_run1.jsonl

## Files


tailor.py              core function
judge.py               AI judge (fabrication check + usable yes/no)
llm.py                 API call helper (Groq or OpenRouter)
eval.py                eval script
judge_check.py         judge vs. my scores
data/resume_v1.txt     my resume as ID-tagged facts 
eval/eval_set.jsonl    50 examples (30 typical, 20 hard)
eval/job_sources.md    links for the postings T01-T15 are based on
eval/tech_terms.txt    technical terms checked for fabrication
eval/human_scores.csv  my hand scores for judge validation
REPORT.md              project report

