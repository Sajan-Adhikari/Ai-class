"""Compare the AI judge's verdicts with your own on a few examples.

1. Run the eval, then open a results/<...>_run1.jsonl file and read some outputs.
2. Fill eval/human_scores.csv: id, my_faithful (yes/no), my_usable (yes/no), notes.
3. python judge_check.py --results results/<...>_run1.jsonl
"""
import argparse
import csv
import json
import os

from llm import ROOT


def yes(text):
    return text.strip().lower() in ("yes", "y", "true", "1")


def load_pairs(results_path, human_path):
    """[{id, me_faithful, judge_faithful, me_usable, judge_usable}] for ids judged by both."""
    with open(results_path, encoding="utf-8") as f:
        judged = {item["id"]: item["judge"] for item in map(json.loads, f)
                  if item["judge"].get("usable") is not None}
    with open(human_path, encoding="utf-8") as f:
        return [{"id": h["id"],
                 "me_faithful": yes(h["my_faithful"]), "judge_faithful": judged[h["id"]]["faithful"],
                 "me_usable": yes(h["my_usable"]), "judge_usable": judged[h["id"]]["usable"]}
                for h in csv.DictReader(f) if h["id"] in judged and h["my_usable"].strip()]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True, help="a results/..._runN.jsonl file")
    p.add_argument("--human", default=os.path.join(ROOT, "eval", "human_scores.csv"))
    args = p.parse_args()

    rows = load_pairs(args.results, args.human)
    if not rows:
        raise SystemExit("No overlapping scored examples. Fill eval/human_scores.csv with ids from the results file.")

    print(f"{'id':<6}{'me: faithful':<14}{'judge':<8}{'me: usable':<12}{'judge':<6}")
    for r in rows:
        print(f"{r['id']:<6}{str(r['me_faithful']):<14}{str(r['judge_faithful']):<8}"
              f"{str(r['me_usable']):<12}{str(r['judge_usable']):<6}")

    n = len(rows)
    for label, key in (("Faithfulness agreement", "faithful"), ("Usable agreement", "usable")):
        agree = sum(r[f"me_{key}"] == r[f"judge_{key}"] for r in rows)
        print(f"{label + ':':<26}{100 * agree / n:.0f}%  ({agree}/{n})")
    print(f"{'Examples compared:':<26}{n}")


if __name__ == "__main__":
    main()
