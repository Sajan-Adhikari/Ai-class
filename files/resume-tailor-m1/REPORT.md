# Resume Tailor: Project Report

 Evaluation method

 For me as a job seeker, a good output is one I would submit as my resume: it uses only my real experience, speaks the posting's language, and honestly flags the skills I don't have. A single fabricated claim makes an output unusable, because being caught overstating on a resume is worse than not applying.

Unit of evaluation. One example = one job description plus an answer key, run against my fixed resume (data/resume_v1.txt. My resume is stored as 36 ID-tagged facts so every tailored bullet must cite the facts it comes from. This turns faithfulness into something checkable.By answer key, it means every field in the eval_set except the job text. This is my first data in eval_set. 
{"id": "T01",
"type": "typical",
"category": "strong_fit",
 "job": "Engineer 1, Merchandise Planning - Nordstrom (Seattle, hybrid 4 days on site). Junior engineer (0-2 years, new grads welcome) building business-critical APIs and web apps on a Java, AWS and GCP stack. Work includes API development, CI/CD automation, unit and behavior-driven tests, design and code reviews, monitoring and alerting, on-call support and root cause analysis. Wants strong object-oriented design, Java with some Python, data structures, distributed systems, REST, microservices, JSON and XML. Nice to have: Spring Boot, Kafka, Docker, Kubernetes, React, NoSQL and AWS.",
 "expected": "tailor",
"should_use": ["N4", "N7|N9", "S4", "P1|N10"],
"must_flag_missing": ["Kubernetes"],
"traps": ["Kubernetes", "on-call"], 
"keywords": ["Java", "Spring Boot", "Kafka", "Docker", "CI/CD", "REST", "microservices", "AWS", "GCP", "Python"], 
"notes": ""}

If we take this example,
job -- This is job description 
expected -- This is a real software job. The model must tailor, not reject. (metric:pass/fail)
should_use --A good answer should cite N4 (the Java and Spring Boot code), S4 (the RESTful services and microservices), either N7 or N9 (the CI/CD pipeline and automation work), and either P1 or N10 (Kafka, AWS and Docker work). (metric:Fact coverage)
must_flag_missing --The posting asks for value "Kubernetes" and resume has none, so the model must list it in missing_skills. (metric:Missing skill recall)
traps --If either word appears in the summary or bullets, that’s fabrication. (metric:faithfullness)
keyword --Job terms a well-targeted answer should echo.



Metrics and scoring.

1. Faithfulness (primary, hard constraint). An output is faithful only if it passes all code checks and the AI judge:
   - Fabrication traps: none of the example's trap terms appear (e.g. "Kubernetes", "managed a team").
   - Unsupported terms: no technical term from `eval/tech_terms.txt` appears unless it is in my resume.
   - Invented numbers: every number in the output also appears in my resume.
   - Sources: every bullet cites real fact IDs, and at least one experience fact (not only the skills list).
   - AI judge: catches what code can't, such as "contributed to" becoming "led", an academic project presented as production work, or a skills-list item presented as work experience.
2. Correct tailor/reject. Non-software jobs, non-job text and empty input must be rejected.
3. Usable (yes/no, AI judge). Would I submit it as-is or after small edits? Any faithfulness problem makes it a no. A yes/no question is more consistent.
4. Fact coverage Share of the facts I marked as most relevant that the output actually uses.
5. Missing-skill recall Share of the required gaps (e.g. Terraform) the output flags.
6. Keyword gain. Share of the job's key terms present in the tailored output minus the share in an untailored baseline of the same length (my original summary + first six work bullets). This is the "did it respond to the posting" proxy from my proposal.

How pass/fail is done:
Each example gets a single 0/1 passed, decided in order. The first rule that applies wins.


1.)The API call failed or the reply couldn’t be read: fail. This includes empty replies, rate limits, and bad JSON.
2.)The model rejected the job: pass if expected allows rejecting, and fail otherwise. Nothing else is checked, because there’s no resume to grade.
3.)The model tailored a job that should be rejected (the picnic notice, nursing, empty input): fail.
4.)The model tailored a job that should be tailored: now the output itself is graded in two layers.

a. Code checks. All of these must be true:

-no traps word appears in the summary or bullets
-no tech term from tech_terms.txt appears that isn’t in your resume
-no number appears that isn’t in your resume
-every bullet cites real fact IDs, and not only skills or education facts
-the output has at least one bullet

b. Judge. It must answer faithful = yes and usable = yes.

Pass only if both layers pass.


AI judge. One fixed judge model  scores every model under comparison, so differences come from the model being tested.
Judge Prompt:
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


Judge vs. my own scores. I scored 5_ outputs by hand (eval/human_scores.csv) and compared them with the judge using judge_check.py: faithfulness agreement _40_%, usable agreement _40_%. 
I feel the answer are correct overall although because I have more metrics to cover it is bringing down the score.

Eval set 50 examples in eval/eval_set.jsonl.
30 typical: T01-T15 are based on real postings I could apply to .
20 hard: jobs needing skills I lack (Kubernetes platform, iOS, ML); two prompt injections; vague and very short postings; non-software jobs, a non-job notice and an empty input (must reject); seniority bait (managing a team, 8+ years); academic-vs-professional bait (production PostgreSQL/Redis); skills-list-only bait (.NET Core experience); metrics bait (asks for percentages); a long buzzword-heavy posting; a Spanish posting; and two different-domain roles (embedded C++, systems programming).

What the judge sees

Three things, in resume, job and tailored_output tags:resume,job posting and tailor's summary
It does not see the code-check results or the answer key, so it judges independently.

How it decides faithful

The prompt (JUDGE_PROMPT in judge.py) tells it to compare the summary and every bullet with the facts, especially the cited ones, and flag any of these:

-a tool, technology, number, title, team size or domain not in the facts
-inflated strength or scope (“contributed to” → “led”)
-an academic project presented as professional work
-a skills-list (K) item presented as work experience
-any claim the cited facts don’t support

Runs- 
I have ran for only one time
Target for the final _e.g. faithfulness ≥ 70%, pass rate ≥ 80%
## Model selection

Date run: 2026-11-07. Same prompt (v1), temperature 0, eval set and judge (openai/gpt-oss-120b on Groq) for every model. One run.

| Model | Open-weight? | Pass rate %  | Faithfulness % | Hard-case pass % | Usable % | Missing-skill recall % | Avg latency s |
|---|---|---|---|---|---|---|---|
| openai/gpt-oss-20b (Groq) | Yes | 18.0 | 13.3 | 25.0 | 15.6 | 92.0 | 2.38 |
| cohere/north-mini-code:free (OpenRouter) | No | n/a: empty replies (reasoned until the token limit) | | | | | |
| google/gemma-4-31b-it:free (OpenRouter) | Yes | n/a: rate-limited (429) | | | | | |

**Chosen model:** `openai/gpt-oss-20b`

It was the only free model that completed the eval. It makes the right tailor/reject decision (98%), flags almost every missing skill (92%) and is fast (2.4 s), but it overstates my experience in most outputs (faithfulness 13%). Since faithfulness weighs most, I kept the model and worked on the prompt.

## Iteration log

| Date | What changed | Pass rate % | What I learned |
|---|---|---|---|
| 2026-11-07 | Baseline: gpt-oss-20b, full-context prompting (no RAG), 50-example eval set | 18.0  | Decisions and gap-flagging are good; the main failure is inflated wording ("designed" for "contributed to", "scalable", "robust"). |
| 2026-11-07 | Prompt v2: rules on verb strength and added qualities, bad/good examples from my facts, self-check step. Judge told to grade the output, not my fit. Reasoning effort set to low. | Full run pending | On a small test, 2 of 4 previously failing outputs passed. Low reasoning effort fixed empty replies and used about 5× fewer tokens. 

### Three examples the chosen model got wrong

1. T01: judge issue. It wrote "Designed and implemented Java Spring-based web applications", but N2 says "Contributed to the design of".
   _Why I think it failed:_ prompt v1 allowed rewording "to use the job's language", and the model upgraded verbs to sound stronger.
2. H05 (prompt injection): judge issue. It correctly ignored the injected instruction, but it described the academic payment gateway (P1) as "high-throughput payment processing" and turned N5 into "Led the implementation".
   _Why I think it failed:_ it mixed P1 with work facts (N10) in one bullet, which blurred academic and professional work.
3. T17: code check. One bullet cites only D1 (education). The judge missed this.
   _Why I think it failed:_ the new-grad job asked for fundamentals, so the model turned education into an experience bullet.

What I will change first: done in prompt v2. Explicit rules against stronger verbs and added qualities, worked bad/good examples, and a self-check before answering.
