"""Writes BLIND_CASES.txt: the case text only, no answers. Give that file plus READING_FORM_PROMPT.txt to any model."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cases_dev as cd, cases_held as ch
STYLE = {None: "a stranger; no history with this person",
         "terse": "known person; their normal is very short messages (one to four words), quick replies",
         "medium": "known person; their normal is one or two plain sentences, replies in about half a minute",
         "chatty": "known person; their normal is long, playful, exclamation-heavy messages with jokes and questions"}
out = []
for c in cd.DEV + ch.HELD:
    out.append(f"CASE {c['id'].split('_')[0]}")
    out.append(f"  who: {STYLE[c['warm']]}")
    for i, (t, g) in enumerate(c["turns"], 1):
        out.append(f"  turn {i} (after {g} seconds): {t}")
    out.append("")
open(os.path.join(sys.argv[1], "BLIND_CASES.txt"), "w", encoding="utf-8").write("\n".join(out))
print(len(cd.DEV) + len(ch.HELD), "cases written")
