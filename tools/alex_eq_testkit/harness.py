"""Harness: runs readers over multi-turn synthetic cases and scores the READING and the MOVE separately.

Usage:  python3 -I harness.py <path-to-source/modules> <dev|held|both> [self_report_weight]
A "reader" is any object with  start(case)  and  step(text, ts) -> dict(p=float, move=str, gap=bool, note=str)
p = probability that something is weighing on the person right now.
"""
import sys, json, math, importlib.util, os

HERE = os.path.dirname(os.path.abspath(__file__))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class ExistingEngineReader:
    """Candidate A: the shipped AffectContextEngine, unchanged. Mapping of its output to this
    harness: p = its confidence when it is in a care state (friction/depletion/disengagement),
    else 0.05. Moves: friction->practical_help, depletion->offer, disengagement->adjust_quietly,
    anything else->carry_on. It has no notion of 'gap'."""
    name = "A_existing_engine"

    def __init__(self, ace):
        self.ace = ace

    def start(self, case):
        self.eng = self.ace.AffectContextEngine()
        self.uid = case["id"]

    def step(self, text, ts):
        out = self.eng.evaluate(text, self.uid, "s", ts=ts)
        st = out["reading"]["state"]
        conf = float(out["reading"]["confidence"])
        care = st in ("friction", "depletion", "disengagement")
        move = {"friction": "practical_help", "depletion": "offer",
                "disengagement": "adjust_quietly"}.get(st, "carry_on")
        return dict(p=conf if care else 0.05, move=move, gap=False, note=f"{st}@{conf:.2f}")


def run_case(reader, case, warm_pools):
    reader.start(case)
    ts = 1_700_000_000.0
    for text, gap_s in (warm_pools.get(case["warm"]) or []):
        ts += gap_s
        reader.step(text, ts)
    ts += 3600 * 20  # the test turns happen the next day
    trace = []
    for text, gap_s in case["turns"]:
        ts += gap_s
        trace.append(reader.step(text, ts))
    return trace


def score(case, trace):
    last = trace[-1]
    truth = 1.0 if case["load"] >= 1 else 0.0
    brier = (last["p"] - truth) ** 2
    # three bands: quiet (<0.35), noticed (0.35-0.6), strong (>=0.6).
    # nothing weighing -> must stay quiet; something -> must at least be noticed; heavy -> must be strong.
    need = {0: None, 1: 0.35, 2: 0.60}[case["load"]]
    detect = (last["p"] < 0.35) if need is None else (last["p"] >= need)
    early = None
    if case.get("by"):
        early = any(t["p"] >= 0.35 for t in trace[:case["by"]])
    premature = None
    if case.get("not_before"):
        premature = any(t["p"] >= 0.35 for t in trace[:case["not_before"] - 1])
    move_ok = last["move"] in case["ok"]
    move_bad = last["move"] in case["bad"]
    gap_ok = (bool(last.get("gap")) == bool(case["gap"]))
    return dict(brier=brier, detect=detect, early=early, premature=premature,
                move_ok=move_ok, move_bad=move_bad, gap_ok=gap_ok)


def report(name, cases, results, verbose=True):
    n = len(cases)
    br = sum(r["brier"] for r in results) / n
    det = sum(r["detect"] for r in results)
    e = [r["early"] for r in results if r["early"] is not None]
    pm = [r["premature"] for r in results if r["premature"] is not None]
    mo = sum(r["move_ok"] for r in results)
    mb = sum(r["move_bad"] for r in results)
    gp = [r["gap_ok"] for r, c in zip(results, cases) if c["gap"]]
    gfp = sum(1 for r, c in zip(results, cases) if not c["gap"] and not r["gap_ok"])
    luck = sum(1 for r in results if r["move_ok"] and not r["detect"])
    fa = sum(1 for r, c in zip(results, cases) if c["load"] == 0 and not r["detect"])
    nz = sum(1 for c in cases if c["load"] == 0)
    miss = sum(1 for r, c in zip(results, cases) if c["load"] >= 1 and not r["detect"])
    print(f"\n== {name}  (n={n})")
    print(f"  reading right at last turn : {det}/{n}   (missed {miss} of {n-nz} loaded cases; false alarm on {fa} of {nz} unloaded)")
    print(f"  Brier score (lower better) : {br:.3f}")
    print(f"  read in time (by turn)     : {sum(e)}/{len(e)}")
    if pm:
        print(f"  fired too early            : {sum(pm)}/{len(pm)}")
    print(f"  say/show gap caught        : {sum(gp)}/{len(gp)}   false gap flags: {gfp}")
    print(f"  move fits                  : {mo}/{n}   move is a clear miss: {mb}/{n}")
    print(f"  good move on wrong reading : {luck}  (luck, not understanding)")
    return dict(name=name, n=n, detect=det, brier=round(br, 3), early=f"{sum(e)}/{len(e)}",
                gap=f"{sum(gp)}/{len(gp)}", false_gap=gfp, move_ok=mo, move_bad=mb, luck=luck,
                false_alarm=f"{fa}/{nz}", missed=f"{miss}/{n-nz}")


def detail(cases, traces, results):
    for c, tr, r in zip(cases, traces, results):
        ps = " ".join(f"{t['p']:.2f}" for t in tr)
        flag = "ok " if (r["detect"] and r["move_ok"]) else "MISS"
        print(f"  {flag} {c['id']:<28} load={c['load']} p=[{ps}] move={tr[-1]['move']:<17} gap={tr[-1].get('gap')} | {tr[-1]['note'][:70]}")


if __name__ == "__main__":
    src = sys.argv[1]
    which = sys.argv[2] if len(sys.argv) > 2 else "dev"
    w_self = float(sys.argv[3]) if len(sys.argv) > 3 else None
    ace = load_module("affect_context_engine", os.path.join(src, "affect_context_engine.py"))
    cd = load_module("cases_dev", os.path.join(HERE, "cases_dev.py"))
    sets = []
    if which in ("dev", "both"):
        sets.append(("DEV", cd.DEV))
    if which in ("held", "both"):
        ch = load_module("cases_held", os.path.join(HERE, "cases_held.py"))
        sets.append(("HELD-OUT", ch.HELD))
    readers = [ExistingEngineReader(ace)]
    if os.path.exists(os.path.join(HERE, "reader_b.py")):
        rb = load_module("reader_b", os.path.join(HERE, "reader_b.py"))
        kw = {} if w_self is None else {"w_self": w_self}
        readers.append(rb.SituationReader(**kw))
        readers.append(rb.HybridReader(ace, **kw))
    summary = []
    for label, cases in sets:
        for rd in readers:
            traces = [run_case(rd, c, cd.WARM) for c in cases]
            results = [score(c, t) for c, t in zip(cases, traces)]
            s = report(f"{label} / {rd.name}", cases, results)
            s["set"] = label
            summary.append(s)
            if "-q" not in sys.argv:
                detail(cases, traces, results)
    with open(os.path.join(HERE, "last_run_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
