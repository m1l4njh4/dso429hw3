"""Check solver.py against the published practice keys (rounds 1-48)."""

import csv
import io
import urllib.request

from solver import solve

BASE = "https://raw.githubusercontent.com/FaisalXL/dso429-hourly-quiz/main/"


def fetch(name):
    with urllib.request.urlopen(BASE + name, timeout=30) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8"))))


keys = {(r["round_id"], r["q_index"]): r["answer"] for r in fetch("practice_keys.csv")}
right = wrong = unsolved = 0
for q in fetch("questions.csv"):
    k = (q["round_id"], q["q_index"])
    if k not in keys:
        continue
    opts = [q["option_a"], q["option_b"], q["option_c"], q["option_d"]]
    letter, tmpl = solve(q["question_text"], opts)
    if letter is None:
        unsolved += 1
        print("UNSOLVED", k, q["question_text"], opts)
    elif letter == keys[k]:
        right += 1
    else:
        wrong += 1
        print("WRONG", k, tmpl, letter, "key", keys[k], q["question_text"], opts)

print(f"right={right} wrong={wrong} unsolved={unsolved} of {len(keys)}")
