"""Run the eval set through tailor() and print scores.

Usage:
    python eval.py --model openai/gpt-oss-20b --sleep 10           # one full run
    python eval.py --model <id> --limit 5                         # quick test
    python eval.py --model <id> --no-judge                        # code checks only
    python eval.py --model <id> --runs 3                          # final comparison
"""
import argparse
import csv
import json
import os
import re
import statistics
import time
from datetime import datetime

from judge import judge, DEFAULT_JUDGE
from llm import ROOT, load_resume
from tailor import tailor, DEFAULT_MODEL

RESULTS = os.path.join(ROOT, "results")

# Columns of each per-run CSV, in order. Anything score() doesn't fill stays "".
FIELDS = ["id", "type", "category", "expected", "predicted", "passed", "status_ok",
          "code_faithful", "judge_faithful", "faithful", "usable", "coverage",
          "missing_recall", "kw_tailored", "kw_baseline", "kw_gain", "traps_hit",
          "unsupported_terms", "new_numbers", "source_problems", "judge_issues", "error",
          "latency_s", "in_tok", "out_tok", "j_in_tok", "j_out_tok"]


# ---------------------------------------------------------------- loading
def load():
    resume = load_resume()
    facts = dict(re.findall(r"^([A-Z]\d+):\s*(.+)$", resume, re.M))
    # Baseline = an untailored version of the same length: the original summary (S1-S4)
    # plus the first 6 work bullets in their original order (N1-N6).
    baseline = "\n".join(facts[k] for k in ["S1", "S2", "S3", "S4", "N1", "N2", "N3", "N4", "N5", "N6"])
    with open(os.path.join(ROOT, "eval", "tech_terms.txt"), encoding="utf-8") as f:
        terms = [t.strip() for t in f if t.strip() and not t.startswith("#")]
    with open(os.path.join(ROOT, "eval", "eval_set.jsonl"), encoding="utf-8") as f:
        examples = [json.loads(line) for line in f if line.strip()]
    return resume, facts, baseline, terms, examples


# ---------------------------------------------------------------- matching helpers
def has(term, text):
    """Case-insensitive match. Whole-word for terms with letters/digits ('Express' won't match
    'expressed'); plain substring for symbol-only terms like '%'. Used for fabrication checks."""
    if not re.search(r"[A-Za-z0-9]", term):
        return term in text
    pattern = r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])"
    return re.search(pattern, text, re.I) is not None


def group_found(group, text):
    """group = 'Django|FastAPI' -> found if any alternative appears as a case-insensitive
    substring. Deliberately looser than has(): keyword 'test' should match 'testing'."""
    return any(alt.strip().lower() in text.lower() for alt in group.split("|"))


def numbers(text):
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def share(groups, text):
    """Fraction of keyword groups found in text."""
    return sum(group_found(g, text) for g in groups) / len(groups)


# ---------------------------------------------------------------- scoring one example
def source_problems(bullets, facts):
    problems = []
    for i, b in enumerate(bullets, 1):
        bad = [s for s in b["source"] if s not in facts]
        if not b["source"]:
            problems.append(f"bullet {i}: no source")
        elif bad:
            problems.append(f"bullet {i}: unknown {bad}")
        elif all(s[0] in "KD" for s in b["source"]):
            problems.append(f"bullet {i}: only skills/education sources")
    return problems


def score(ex, out, jd, resume, facts, baseline, terms):
    r = dict.fromkeys(FIELDS, "")
    r.update(id=ex["id"], type=ex["type"], category=ex["category"], expected=ex["expected"],
             passed=0, status_ok=0, error=out.get("error") or "")

    if out.get("error"):
        r["predicted"] = "error"
        return r
    pred = "reject" if out["status"] == "reject" else "tailor"
    r["predicted"] = pred
    r["status_ok"] = int(pred in ex["expected"].split("|"))
    if pred == "reject":                       # nothing else to check
        r["passed"] = r["status_ok"]
        return r
    if not r["status_ok"]:                     # tailored something that should be rejected
        return r

    text = out["summary"] + "\n" + "\n".join(b["text"] for b in out["bullets"])

    # --- faithfulness: code checks
    traps = [t for t in ex["traps"] if has(t, text)]
    unsupported = [t for t in terms if has(t, text) and t.lower() not in resume.lower()]
    new_nums = sorted(numbers(text) - numbers(resume))
    src_problems = source_problems(out["bullets"], facts)
    code_ok = not (traps or unsupported or new_nums or src_problems or not out["bullets"])
    r.update(code_faithful=int(code_ok), traps_hit="; ".join(traps),
             unsupported_terms="; ".join(unsupported), new_numbers="; ".join(new_nums),
             source_problems="; ".join(src_problems))

    # --- relevance and coverage
    cited = {s for b in out["bullets"] for s in b["source"]}
    if ex["should_use"]:
        hit = sum(any(a in cited for a in g.split("|")) for g in ex["should_use"])
        r["coverage"] = round(hit / len(ex["should_use"]), 3)
    if ex["must_flag_missing"]:
        r["missing_recall"] = round(share(ex["must_flag_missing"], " ".join(out["missing_skills"])), 3)
    if ex["keywords"]:
        kt, kb = share(ex["keywords"], text), share(ex["keywords"], baseline)
        r.update(kw_tailored=round(kt, 3), kw_baseline=round(kb, 3), kw_gain=round(kt - kb, 3))

    # --- AI judge
    if jd is None:
        r["faithful"] = int(code_ok)
        r["passed"] = int(code_ok and (r["coverage"] == "" or r["coverage"] >= 0.5))
        return r
    if jd.get("error"):
        r["error"] = jd["error"]
    else:
        r.update(judge_faithful=int(jd["faithful"]), usable=int(jd["usable"]),
                 judge_issues="; ".join(jd["issues"]))
    r["faithful"] = int(code_ok and r["judge_faithful"] == 1)
    r["passed"] = int(r["faithful"] and r["usable"] == 1)
    return r


# ---------------------------------------------------------------- summary of one run
def summarize(rows):
    def mean_of(key, subset=None):
        vals = [r[key] for r in (rows if subset is None else subset) if r[key] != ""]
        return 100 * statistics.mean(vals) if vals else None

    tailored = [r for r in rows if r["predicted"] == "tailor" and r["status_ok"]]
    lat = [r["latency_s"] for r in rows if r["latency_s"] is not None]
    return {
        "pass_rate": mean_of("passed"),
        "typical_pass": mean_of("passed", [r for r in rows if r["type"] == "typical"]),
        "hard_pass": mean_of("passed", [r for r in rows if r["type"] == "hard"]),
        "faithfulness": mean_of("faithful", tailored),
        "status_acc": mean_of("status_ok"),
        "coverage": mean_of("coverage"),
        "missing_recall": mean_of("missing_recall"),
        "kw_gain": mean_of("kw_gain"),
        "usable": mean_of("usable", tailored),
        "error_rate": 100 * sum(1 for r in rows if r["error"]) / len(rows),
        "latency": statistics.mean(lat) if lat else None,
    }


# ---------------------------------------------------------------- one run
def run_once(run, examples, args, data):
    """Tailor (and judge) every example once. Returns (score rows, full jsonl records, failed ids)."""
    resume = data[0]
    rows, full, failed = [], [], []
    for i, ex in enumerate(examples, 1):
        out = tailor(resume, ex["job"], model=args.model)
        time.sleep(args.sleep)
        jd = None
        if not args.no_judge and not out.get("error") and out.get("status") == "ok":
            jd = judge(resume, ex["job"], out, model=args.judge_model)
            time.sleep(args.sleep)
        r = score(ex, out, jd, *data)
        j = jd or {}
        r.update(latency_s=out.get("latency_s"), in_tok=out.get("input_tokens", 0),
                 out_tok=out.get("output_tokens", 0),
                 j_in_tok=j.get("input_tokens", 0), j_out_tok=j.get("output_tokens", 0))
        rows.append(r)
        full.append({"id": ex["id"], "run": run,
                     "output": {k: out.get(k) for k in ("status", "reason", "summary", "bullets",
                                                        "missing_skills", "error")},
                     "judge": {k: j.get(k) for k in ("faithful", "issues", "usable", "reason", "error")},
                     "scores": r})
        print(f"  run {run} [{i:02d}/{len(examples)}] {ex['id']} {'PASS' if r['passed'] else 'FAIL'}"
              f"  expected={ex['expected']} got={r['predicted']}"
              + (f" usable={'yes' if r['usable'] else 'no'}" if r['usable'] != "" else "")
              + (f" !{r['error'][:60]}" if r['error'] else ""))
        if not r["passed"]:
            failed.append(ex["id"])
    return rows, full, failed


def write_run_files(base, rows, full):
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    with open(base + ".jsonl", "w", encoding="utf-8") as f:
        for item in full:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- report across runs
def summary_lines(summaries, args):
    def stat(key, fmt="{:.1f}"):
        vals = [s[key] for s in summaries if s[key] is not None]
        if not vals:
            return "n/a"
        m = fmt.format(statistics.mean(vals))
        return m if len(vals) == 1 else f"{m} (range {fmt.format(min(vals))}-{fmt.format(max(vals))})"

    lines = [
        ("Pass rate (%)", stat("pass_rate")),
        ("  Typical (%)", stat("typical_pass")),
        ("  Hard (%)", stat("hard_pass")),
        ("Faithfulness (%)", stat("faithfulness")),
        ("Correct tailor/reject (%)", stat("status_acc")),
        ("Fact coverage (%)", stat("coverage")),
        ("Missing-skill recall (%)", stat("missing_recall")),
        ("Keyword gain vs baseline (pts)", stat("kw_gain")),
    ]
    if not args.no_judge:
        lines.append(("Usable, judge (%)", stat("usable")))
    lines += [
        ("Error rate (%)", stat("error_rate")),
        ("Avg latency (s)", stat("latency", "{:.2f}")),
    ]
    return lines


def append_summary_csv(tag, args, lines):
    path = os.path.join(RESULTS, "summary.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["run_tag", "model", "judge", "runs"] + [n.strip() for n, _ in lines])
        w.writerow([tag, args.model, "off" if args.no_judge else args.judge_model, args.runs]
                   + [v for _, v in lines])
    return path


# ---------------------------------------------------------------- main
def parse_args():
    p = argparse.ArgumentParser(description="Evaluate tailor() on the eval set.")
    p.add_argument("--model", default=DEFAULT_MODEL, help="OpenRouter model id to evaluate")
    p.add_argument("--judge-model", default=DEFAULT_JUDGE, help="fixed judge model id")
    p.add_argument("--no-judge", action="store_true", help="code checks only")
    p.add_argument("--runs", type=int, default=1, help="repeat the eval N times (use 3 for the final)")
    p.add_argument("--limit", type=int, default=0, help="only the first N examples")
    p.add_argument("--only", default="", help="comma-separated example ids, e.g. T01,H04")
    p.add_argument("--sleep", type=float, default=0.0, help="pause between calls (free tiers: 3-15)")
    return p.parse_args()


def main():
    args = parse_args()
    *data, examples = load()   # data = resume, facts, baseline, terms
    if args.only:
        keep = set(args.only.split(","))
        examples = [e for e in examples if e["id"] in keep]
    if args.limit:
        examples = examples[: args.limit]

    print(f"Model: {args.model} | judge: {'off' if args.no_judge else args.judge_model} | "
          f"examples: {len(examples)} | runs: {args.runs}")
    os.makedirs(RESULTS, exist_ok=True)
    tag = f"{args.model.replace('/', '_').replace(':', '_')}_{datetime.now():%Y%m%d-%H%M%S}"

    summaries, fails = [], {}
    for run in range(1, args.runs + 1):
        rows, full, failed = run_once(run, examples, args, data)
        for ex_id in failed:
            fails[ex_id] = fails.get(ex_id, 0) + 1
        base = os.path.join(RESULTS, f"{tag}_run{run}")
        write_run_files(base, rows, full)
        s = summarize(rows)
        summaries.append(s)
        print(f"Run {run}: pass {s['pass_rate']:.1f}% | saved {base}.csv/.jsonl")

    lines = summary_lines(summaries, args)
    print("\n" + "=" * 20 + " SUMMARY " + "=" * 20)
    print(f"Model: {args.model}")
    for name, val in lines:
        print(f"{name:<32}{val}")
    if fails:
        print("\nFailed examples (times failed / runs):")
        for ex_id, n in sorted(fails.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {ex_id}: {n}/{args.runs}")
    print(f"\nSummary appended to {append_summary_csv(tag, args, lines)}")


if __name__ == "__main__":
    main()
