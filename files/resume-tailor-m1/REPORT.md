# Resume Tailor: Project Report

## Evaluation method

**What "good" means.** For me as a job seeker, a good output is one I would submit: it uses only my real experience, speaks the posting's language, and honestly flags the skills I don't have. A single fabricated claim makes an output unusable, because being caught overstating on a resume is worse than not applying.

**Unit of evaluation.** One example = one job description plus an answer key, run against my fixed resume (`data/resume_v1.txt`, version 1). My resume is stored as 36 ID-tagged facts so every tailored bullet must cite the facts it comes from. This turns faithfulness into something checkable.

**Metrics and scoring.**

1. **Faithfulness (primary, hard constraint).** An output is faithful only if it passes all code checks *and* the AI judge:
   - *Fabrication traps:* none of the example's trap terms appear (e.g. "Kubernetes", "managed a team").
   - *Unsupported terms:* no technical term from `eval/tech_terms.txt` appears unless it is in my resume.
   - *Invented numbers:* every number in the output also appears in my resume.
   - *Sources:* every bullet cites real fact IDs, and at least one experience fact (not only the skills list).
   - *AI judge:* catches what code can't, such as "contributed to" becoming "led", an academic project presented as production work, or a skills-list item presented as work experience.
2. **Correct tailor/reject.** Non-software jobs, non-job text and empty input must be rejected.
3. **Usability (1-5, AI judge).** 5 = submit as-is, 3 = small edits, 1 = unusable; any faithfulness problem caps it at 2.
4. **Fact coverage.** Share of the facts I marked as most relevant that the output actually uses.
5. **Missing-skill recall.** Share of the required gaps (e.g. Terraform) the output flags.
6. **Keyword gain.** Share of the job's key terms present in the tailored output minus the share in an untailored baseline of the same length (my original summary + first six work bullets). This is the "did it respond to the posting" proxy from my proposal.

An example **passes** if it is correctly tailored or rejected, faithful, and rated usable (≥ 3). Pass rate is reported overall and separately for typical and hard cases.

**AI judge.** One fixed judge model (_[JUDGE_MODEL]_) scores every model under comparison, so differences come from the model being tested. Judge prompt (from `judge.py`):

> _[Paste JUDGE_PROMPT from judge.py here]_

**Judge vs. my own scores.** I scored _[n ≥ 5]_ outputs by hand (`eval/human_scores.csv`) and compared them with the judge using `judge_check.py`: faithfulness agreement _[x]_%, usability within ±1 _[y]_%, mean absolute difference _[z]_. _[One sentence on where you and the judge disagreed.]_

**Eval set.** 50 examples in `eval/eval_set.jsonl`.
- **30 typical:** T01-T15 are based on real postings I could apply to (sources in `eval/job_sources.md`), including Nordstrom, Blue Origin, TSMC Washington, Solace Health, WGU, Smartsheet, State Street, two Washington State agency roles near Lacey (DSHS, Ecology), and senior roles that test seniority claims (Alarm.com/EnergyHub, Kunai, CSCI Consulting, Coforge, Implicit). T16-T30 are postings I wrote, covering partial and weak fits (.NET, Node.js, Golang, Unity, Kotlin, GCP and others).
- **20 hard:** jobs needing skills I lack (Kubernetes platform, iOS, ML); two prompt injections; vague and very short postings; non-software jobs, a non-job notice and an empty input (must reject); seniority bait (managing a team, 8+ years); academic-vs-professional bait (production PostgreSQL/Redis); skills-list-only bait (.NET Core experience); metrics bait (asks for percentages); a long buzzword-heavy posting; a Spanish posting; and two different-domain roles (embedded C++, systems programming).

Each example lists the facts that should be used, the skills that must be flagged as missing, fabrication traps, the job's key terms, and the expected behavior (tailor or reject).

**Runs.** Each model runs the full set 3 times at temperature 0; I report the mean and range.

**Target for the final.** _[e.g. faithfulness ≥ 98%, pass rate ≥ 80%, hard-case pass rate ≥ 70%, missing-skill recall ≥ 85%, positive keyword gain.]_

## Model selection

Date run: _[YYYY-MM-DD]_. Same prompt, temperature 0, eval set and judge for every model.

| Model | Open-weight? | Pass rate % (mean, range) | Faithfulness % | Hard-case pass % | Usability (1-5) | Missing-skill recall % | Avg latency s | Cost / 1k requests |
|---|---|---|---|---|---|---|---|---|
| _[model 1]_ | | | | | | | | |
| _[model 2]_ | | | | | | | | |
| _[model 3]_ | | | | | | | | |

_`:free` variants cost $0; the paid-variant price is shown in brackets as the cost at scale. Judge cost per 1k requests: $[x]._

**Chosen model:** _[model]_

_[One paragraph: why this model, which trade-off you accepted (faithfulness vs. usability vs. latency vs. cost), and how it follows from the table. Faithfulness should weigh most.]_

## Iteration log

| Date | What changed | Pass rate % (mean) | What I learned |
|---|---|---|---|
| _[YYYY-MM-DD]_ | Baseline: _[model]_, prompt v1, full-context prompting (no RAG), 50-example eval set | | |

### Three examples the chosen model got wrong

_(Use the "Failed examples" list from `eval.py` and the full outputs in `results/..._run1.jsonl`.)_

1. **_[Example ID]_** - _[what it got wrong: trap hit / invented number / judge issue / wrong reject]_.
   _Why I think it failed:_ ...
2. **_[Example ID]_** - ...
   _Why I think it failed:_ ...
3. **_[Example ID]_** - ...
   _Why I think it failed:_ ...

**What I will change first:** _[e.g. add a worked example to the prompt, tighten the rule on skills-list items, add a verify step]_
