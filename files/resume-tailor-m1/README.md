# Resume Tailor

Given a job description and my resume, this tool writes a tailored professional summary and resume bullets using only my real experience, and flags the skills the job asks for that my resume doesn't support.

## Install

```bash
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```

Edit `.env`:
```
OPENROUTER_API_KEY=your_key_here
TAILOR_MODEL=google/gemma-4-31b-it:free     # model being evaluated (default)
JUDGE_MODEL=anthropic/claude-haiku-5.5      # fixed AI judge
```
Model IDs: https://openrouter.ai/models

## Core function

`tailor.py` -> `tailor(resume_text, job_description, model=None)` sends my resume facts (`data/resume_v1.txt`) and one job description to an LLM and returns:

```json
{"status": "ok", "summary": "...",
 "bullets": [{"text": "...", "source": ["N4"]}],
 "missing_skills": ["Kubernetes"]}
```

Every bullet cites the resume fact IDs it is based on. The model is a setting (`model=` or `TAILOR_MODEL`), never hard-coded.

Try it on one job:
```bash
python tailor.py my_job.txt
```

## Run the eval (one command)

```bash
python eval.py --model google/gemma-4-31b-it:free --runs 3 --sleep 3
```

Switch models with `--model` only. Quick test first: `python eval.py --model <id> --limit 5 --runs 1`.

| Option | Meaning |
|---|---|
| `--model` | model to evaluate (default `TAILOR_MODEL`) |
| `--judge-model` | AI judge model (default `JUDGE_MODEL`); keep it the same for every model you compare |
| `--no-judge` | code checks only (no judge calls) |
| `--runs` | repeat the full eval N times (default 3) |
| `--sleep` | seconds between calls; use 3 for `:free` models (20 requests/min) |
| `--limit` / `--only T01,H04` | run a subset |
| `--price-in` / `--price-out` | override prices, USD per 1M tokens |

It prints pass rate (overall, typical, hard), faithfulness, tailor/reject accuracy, fact coverage, missing-skill recall, keyword gain vs. the untailored resume, judge usability, latency and cost per 1,000 requests (mean and range across runs), plus the examples that failed. Per-example scores (`.csv`) and full outputs (`.jsonl`) go to `results/`; one line per eval is appended to `results/summary.csv`.

## Check the AI judge against my own scores

1. Read some outputs in a `results/..._run1.jsonl` file.
2. Fill `eval/human_scores.csv` (my_faithful yes/no, my_usability 1-5).
3. `python judge_check.py --results results/<file>_run1.jsonl`

## Files

```
tailor.py              core function
judge.py               AI judge (fabrication check + usability 1-5)
llm.py                 OpenRouter call helper
eval.py                eval script
judge_check.py         judge vs. my scores
data/resume_v1.txt     my resume as ID-tagged facts 
eval/eval_set.jsonl    50 examples (30 typical, 20 hard)
eval/job_sources.md    links for the postings T01-T15 are based on
eval/tech_terms.txt    technical terms checked for fabrication
eval/human_scores.csv  my hand scores for judge validation
REPORT.md              project report
```
