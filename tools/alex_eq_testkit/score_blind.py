"""Scores a model's answers to BLIND_CASES.txt.
Usage: python3 score_blind.py answers.txt
answers.txt has one line per case:   D01 | heavy | no | acknowledge
  (case number | weighing: none/some/heavy | gap: yes/no | move)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cases_dev as cd, cases_held as ch
truth = {c["id"].split("_")[0]: c for c in cd.DEV + ch.HELD}
LV = {"none": 0, "some": 1, "heavy": 2}
rows = {}
for line in open(sys.argv[1], encoding="utf-8"):
    parts = [p.strip().lower() for p in line.split("|")]
    if len(parts) >= 4 and parts[0].upper() in truth:
        rows[parts[0].upper()] = parts
for label, pick in (("DEVELOPMENT (D)", "D"), ("HELD-OUT (H)", "H")):
    ids = [k for k in truth if k.startswith(pick)]
    n = read = exact = gapok = gapn = fit = miss = luck = absent = 0
    for k in ids:
        c = truth[k]; n += 1
        if k not in rows:
            absent += 1; continue
        _, w, g, m = rows[k][:4]
        lv = LV.get(w, -1)
        r = (lv == 0) if c["load"] == 0 else (lv >= 1)
        read += r; exact += (lv == c["load"])
        if c["gap"]:
            gapn += 1; gapok += (g.startswith("y"))
        f = m in c["ok"]; fit += f; miss += (m in c["bad"]); luck += (f and not r)
        if not (r and f):
            print(f"   check {c['id']}: said {w}/{g}/{m}; truth load={c['load']} gap={c['gap']} fits={sorted(c['ok'])}")
    print(f"{label}: n={n} unanswered={absent} | noticed-or-not right {read}/{n} | exact level {exact}/{n} | "
          f"gap caught {gapok}/{gapn} | move fits {fit}/{n} | clear miss {miss}/{n} | good move on wrong reading {luck}")
