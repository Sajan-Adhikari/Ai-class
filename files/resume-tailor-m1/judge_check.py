"""Compare the AI judge's scores with your own scores on a few examples.

1. Run the eval, then open a results/<...>_run1.jsonl file and read some outputs.
2. Fill eval/human_scores.csv: id, my_faithful (yes/no), my_usability (1-5), notes.
3. python judge_check.py --results results/<...>_run1.jsonl
"""
import argparse
import csv
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

p = argparse.ArgumentParser()
p.add_argument("--results", required=True, help="a results/..._runN.jsonl file")
p.add_argument("--human", default=os.path.join(ROOT, "eval", "human_scores.csv"))
args = p.parse_args()

judged = {}
with open(args.results, encoding="utf-8") as f:
    for line in f:
        item = json.loads(line)
        if item["judge"].get("usability") is not None:
            judged[item["id"]] = item["judge"]

rows = []
with open(args.human, encoding="utf-8") as f:
    for h in csv.DictReader(f):
        if h["id"] in judged and h["my_usability"].strip():
            j = judged[h["id"]]
            rows.append((h["id"], h["my_faithful"].strip().lower() in ("yes", "y", "true", "1"),
                         int(h["my_usability"]), j["faithful"], j["usability"]))

if not rows:
    raise SystemExit("No overlapping scored examples. Fill eval/human_scores.csv with ids from the results file.")

print(f"{'id':<6}{'me: faithful':<14}{'judge':<8}{'me: usab.':<11}{'judge':<6}")
for r in rows:
    print(f"{r[0]:<6}{str(r[1]):<14}{str(r[3]):<8}{r[2]:<11}{r[4]:<6}")
n = len(rows)
print(f"\nExamples compared:          {n}")
print(f"Faithfulness agreement:     {100 * sum(r[1] == r[3] for r in rows) / n:.0f}%")
print(f"Usability exact agreement:  {100 * sum(r[2] == r[4] for r in rows) / n:.0f}%")
print(f"Usability within +/-1:      {100 * sum(abs(r[2] - r[4]) <= 1 for r in rows) / n:.0f}%")
print(f"Mean absolute difference:   {sum(abs(r[2] - r[4]) for r in rows) / n:.2f}")
