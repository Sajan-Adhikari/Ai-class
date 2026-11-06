"""Run the eval set through tailor() and print scores.

Usage:
    python eval.py --model google/gemma-4-31b-it:free --runs 3 --sleep 3
    python eval.py --model <id> --limit 5 --runs 1          # quick test
    python eval.py --model <id> --no-judge                  # code checks only
"""
import argparse
import csv
import json
import os
import re
import statistics
import time
from datetime import datetime

import requests

from tailor import tailor, DEFAULT_MODEL
from judge import judge, DEFAULT_JUDGE

ROOT = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- loading
def load():
    resume = open(os.path.join(ROOT, "data", "resume_v1.txt"), encoding="utf-8").read()
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
    'expressed'); plain substring for symbol-only terms like '%'."""
    if not re.search(r"[A-Za-z0-9]", term):
        return term in text
    pattern = r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])"
    return re.search(pattern, text, re.I) is not None


def group_found(group, text):
    """group = 'Django|FastAPI' -> found if any alternative appears (substring, case-insensitive)."""
    return any(alt.strip().lower() in text.lower() for alt in group.split("|"))


def numbers(text):
    return set(re.findall(r"\d+(?:\.\d+)?", text))


# ---------------------------------------------------------------- scoring one example
def score(ex, out, jd, resume, facts, baseline, terms):
    allowed = ex["expected"].split("|")
    r = {"id": ex["id"], "type": ex["type"], "category": ex["category"],
         "expected": ex["expected"], "predicted": "", "passed": 0,
         "status_ok": 0, "code_faithful": "", "judge_faithful": "", "faithful": "",
         "usability": "", "coverage": "", "missing_recall": "", "kw_tailored": "",
         "kw_baseline": "", "kw_gain": "", "traps_hit": "", "unsupported_terms": "",
         "new_numbers": "", "source_problems": "", "judge_issues": "", "error": out.get("error") or ""}

    if out.get("error"):
        r["predicted"] = "error"
        return r
    pred = "reject" if out["status"] == "reject" else "tailor"
    r["predicted"] = pred
    r["status_ok"] = int(pred in allowed)
    if pred == "reject":                       # nothing else to check
        r["passed"] = r["status_ok"]
        return r
    if not r["status_ok"]:                     # tailored something that should be rejected
        return r

    text = out["summary"] + "\n" + "\n".join(b["text"] for b in out["bullets"])
    resume_l = resume.lower()

    # --- faithfulness: code checks
    traps = [t for t in ex["traps"] if has(t, text)]
    unsupported = [t for t in terms if has(t, text) and t.lower() not in resume_l]
    new_nums = sorted(numbers(text) - numbers(resume))
    src_problems = []
    for i, b in enumerate(out["bullets"], 1):
        bad = [s for s in b["source"] if s not in facts]
        if not b["source"]:
            src_problems.append(f"bullet {i}: no source")
        elif bad:
            src_problems.append(f"bullet {i}: unknown {bad}")
        elif all(s[0] in "KD" for s in b["source"]):
            src_problems.append(f"bullet {i}: only skills/education sources")
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
        flagged = " ".join(out["missing_skills"])
        r["missing_recall"] = round(sum(group_found(g, flagged) for g in ex["must_flag_missing"])
                                    / len(ex["must_flag_missing"]), 3)
    if ex["keywords"]:
        kt = sum(group_found(k, text) for k in ex["keywords"]) / len(ex["keywords"])
        kb = sum(group_found(k, baseline) for k in ex["keywords"]) / len(ex["keywords"])
        r.update(kw_tailored=round(kt, 3), kw_baseline=round(kb, 3), kw_gain=round(kt - kb, 3))

    # --- AI judge
    if jd is not None:
        if jd.get("error"):
            r["error"] = jd["error"]
        else:
            r["judge_faithful"] = int(jd["faithful"])
            r["usability"] = jd["usability"]
            r["judge_issues"] = "; ".join(jd["issues"])

    faithful = code_ok and (jd is None or r["judge_faithful"] == 1)
    r["faithful"] = int(faithful)
    if jd is None:
        r["passed"] = int(faithful and (r["coverage"] == "" or r["coverage"] >= 0.5))
    else:
        r["passed"] = int(faithful and r["usability"] != "" and r["usability"] >= 3)
    return r


# ---------------------------------------------------------------- pricing
_MODELS = None


def prices(model):
    """USD per token (input, output) from OpenRouter's public model list."""
    global _MODELS
    try:
        if _MODELS is None:
            _MODELS = requests.get("https://openrouter.ai/api/v1/models", timeout=15).json()["data"]
        for m in _MODELS:
            if m["id"] == model:
                return float(m["pricing"]["prompt"]), float(m["pricing"]["completion"])
    except Exception:
        pass
    return None, None


def cost_per_1k(rows, key_in, key_out, p_in, p_out):
    if p_in is None or not rows:
        return None
    return 1000 * (statistics.mean(r[key_in] for r in rows) * p_in
                   + statistics.mean(r[key_out] for r in rows) * p_out)


# ---------------------------------------------------------------- summary of one run
def summarize(rows, price):
    def mean_of(key, subset=None):
        vals = [r[key] for r in (subset or rows) if r[key] != ""]
        return 100 * statistics.mean(vals) if vals else None

    tailored = [r for r in rows if r["predicted"] == "tailor" and r["status_ok"]]
    usab = [r["usability"] for r in rows if r["usability"] != ""]
    lat = [r["latency_s"] for r in rows if r["latency_s"] is not None]
    return {
        "pass_rate": mean_of("passed"),
        "typical_pass": mean_of("passed", [r for r in rows if r["type"] == "typical"]),
        "hard_pass": mean_of("passed", [r for r in rows if r["type"] == "hard"]),
        "status_acc": mean_of("status_ok"),
        "faithfulness": mean_of("faithful", tailored) if tailored else None,
        "code_faithfulness": mean_of("code_faithful", tailored) if tailored else None,
        "coverage": mean_of("coverage"),
        "missing_recall": mean_of("missing_recall"),
        "kw_gain": mean_of("kw_gain"),
        "usability": statistics.mean(usab) if usab else None,
        "usable_pct": 100 * sum(u >= 3 for u in usab) / len(usab) if usab else None,
        "error_rate": 100 * sum(1 for r in rows if r["error"]) / len(rows),
        "latency": statistics.mean(lat) if lat else None,
        "cost_1k": cost_per_1k(rows, "in_tok", "out_tok", *price["model"]),
        "paid_cost_1k": cost_per_1k(rows, "in_tok", "out_tok", *price["paid"]),
        "judge_cost_1k": cost_per_1k(rows, "j_in_tok", "j_out_tok", *price["judge"]),
    }


# ---------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description="Evaluate tailor() on the eval set.")
    p.add_argument("--model", default=DEFAULT_MODEL, help="OpenRouter model id to evaluate")
    p.add_argument("--judge-model", default=DEFAULT_JUDGE, help="fixed judge model id")
    p.add_argument("--no-judge", action="store_true", help="code checks only")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--limit", type=int, default=0, help="only the first N examples")
    p.add_argument("--only", default="", help="comma-separated example ids, e.g. T01,H04")
    p.add_argument("--sleep", type=float, default=0.0, help="pause between calls (use 3 for :free)")
    p.add_argument("--price-in", type=float, help="override USD per 1M input tokens")
    p.add_argument("--price-out", type=float, help="override USD per 1M output tokens")
    args = p.parse_args()

    resume, facts, baseline, terms, examples = load()
    if args.only:
        keep = set(args.only.split(","))
        examples = [e for e in examples if e["id"] in keep]
    if args.limit:
        examples = examples[: args.limit]

    price = {"model": prices(args.model), "paid": (None, None), "judge": prices(args.judge_model)}
    if args.price_in is not None and args.price_out is not None:
        price["model"] = (args.price_in / 1e6, args.price_out / 1e6)
    if args.model.endswith(":free"):
        price["paid"] = prices(args.model[: -len(":free")])

    use_judge = not args.no_judge
    print(f"Model: {args.model} | judge: {args.judge_model if use_judge else 'off'} | "
          f"examples: {len(examples)} | runs: {args.runs}")
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    tag = f"{args.model.replace('/', '_').replace(':', '_')}_{datetime.now():%Y%m%d-%H%M%S}"

    summaries, fails = [], {}
    for run in range(1, args.runs + 1):
        rows, full = [], []
        for i, ex in enumerate(examples, 1):
            out = tailor(resume, ex["job"], model=args.model)
            time.sleep(args.sleep)
            jd = None
            if use_judge and not out.get("error") and out.get("status") == "ok":
                jd = judge(resume, ex["job"], out, model=args.judge_model)
                time.sleep(args.sleep)
            r = score(ex, out, jd, resume, facts, baseline, terms)
            r.update(latency_s=out.get("latency_s"), in_tok=out.get("input_tokens", 0),
                     out_tok=out.get("output_tokens", 0),
                     j_in_tok=(jd or {}).get("input_tokens", 0), j_out_tok=(jd or {}).get("output_tokens", 0))
            rows.append(r)
            full.append({"id": ex["id"], "run": run, "output": {k: out.get(k) for k in
                         ("status", "reason", "summary", "bullets", "missing_skills", "error")},
                         "judge": {k: (jd or {}).get(k) for k in ("faithful", "issues", "usability", "reason", "error")},
                         "scores": r})
            print(f"  run {run} [{i:02d}/{len(examples)}] {ex['id']} {'PASS' if r['passed'] else 'FAIL'}"
                  f"  expected={ex['expected']} got={r['predicted']}"
                  + (f" usability={r['usability']}" if r['usability'] != "" else "")
                  + (f" !{r['error'][:60]}" if r['error'] else ""))
            if not r["passed"]:
                fails[ex["id"]] = fails.get(ex["id"], 0) + 1

        base = os.path.join(ROOT, "results", f"{tag}_run{run}")
        with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)
        with open(base + ".jsonl", "w", encoding="utf-8") as f:
            for item in full:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        s = summarize(rows, price)
        summaries.append(s)
        print(f"Run {run}: pass {s['pass_rate']:.1f}% | saved {base}.csv/.jsonl")

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
        ("  Code checks only (%)", stat("code_faithfulness")),
        ("Correct tailor/reject (%)", stat("status_acc")),
        ("Fact coverage (%)", stat("coverage")),
        ("Missing-skill recall (%)", stat("missing_recall")),
        ("Keyword gain vs baseline (pts)", stat("kw_gain")),
        ("Usability (1-5)", stat("usability", "{:.2f}")),
        ("  Usable, score >= 3 (%)", stat("usable_pct")),
        ("Error rate (%)", stat("error_rate")),
        ("Avg latency (s)", stat("latency", "{:.2f}")),
        ("Cost / 1k requests ($)", stat("cost_1k", "{:.3f}")),
    ]
    if args.model.endswith(":free"):
        lines.append(("  Paid-variant cost / 1k ($)", stat("paid_cost_1k", "{:.3f}")))
    if use_judge:
        lines.append(("Judge cost / 1k requests ($)", stat("judge_cost_1k", "{:.3f}")))

    print("\n" + "=" * 20 + " SUMMARY " + "=" * 20)
    print(f"Model: {args.model}")
    for name, val in lines:
        print(f"{name:<32}{val}")
    if fails:
        print("\nFailed examples (times failed / runs):")
        for ex_id, n in sorted(fails.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {ex_id}: {n}/{args.runs}")

    path = os.path.join(ROOT, "results", "summary.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["run_tag", "model", "judge", "runs"] + [n.strip() for n, _ in lines])
        w.writerow([tag, args.model, args.judge_model if use_judge else "off", args.runs]
                   + [v for _, v in lines])
    print(f"\nSummary appended to {path}")


if __name__ == "__main__":
    main()
