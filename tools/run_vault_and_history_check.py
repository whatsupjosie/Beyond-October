"""Exercise the parts of pubpartner_core.py that can run from the study package:
VerbatimVault (exact saving, tamper check) and the saved-history window.
Modules missing from the package are replaced with empty stand-ins; none of them is used by the code under test."""
import sys, types, importlib.util, json, tempfile, os
from pathlib import Path
from unittest.mock import MagicMock
SRC = Path(sys.argv[1])
pkg = types.ModuleType("modules"); pkg.__path__ = [str(SRC)]; sys.modules["modules"] = pkg
for name in ("turn_serialization", "pubpartner_provider", "pubpartner_profiles", "pubpartner_tokens",
             "pubpartner_receipts", "pubpartner_knowledge", "companion_advisory", "jeremy_cricket",
             "pubpartner_guidance", "pubpartner_vessel", "alex_jeremy_bridge"):
    m = MagicMock(); sys.modules["modules." + name] = m
sys.modules["modules.turn_serialization"].serialized_turn = lambda f: f
spec = importlib.util.spec_from_file_location("modules.pubpartner_core", SRC / "pubpartner_core.py")
core = importlib.util.module_from_spec(spec); sys.modules["modules.pubpartner_core"] = core; spec.loader.exec_module(core)

tmp = Path(tempfile.mkdtemp())
vault = core.VerbatimVault(tmp)
samples = ["plain line", "trailing newline\n", "windows\r\nline endings\r\n", "  leading and trailing spaces  ",
           "curly “quotes”, em dash —, emoji \U0001F643, accents Feic Mo Chroí", "x" * 200_000, "tabs\tand\x0bodd"]
ok = 0
for s in samples:
    rec = vault.store(user_id="synthetic", session_id="s1", text=s)
    back = vault.load(user_id="synthetic", session_id="s1", source_id=rec.source_id)
    ok += (back.text == s and back.sha256 == rec.sha256)
print(f"VAULT exact round trip: {ok}/{len(samples)}")
print("VAULT audit before tamper:", {k: v for k, v in vault.verify_session_audit(user_id='synthetic', session_id='s1').items() if k in ('ok','count','errors','verified','problems')})
raw = next(p for p in vault._session_dir("synthetic", "s1").rglob("*.utf8"))
raw.write_bytes(raw.read_bytes() + b" tampered")
res = vault.verify_session_audit(user_id="synthetic", session_id="s1")
print("VAULT audit after editing one saved file: ok =", res.get("ok"), "| keys:", sorted(res)[:8])
try:
    sid = raw.name.split(".")[0]
    vault.load(user_id="synthetic", session_id="s1", source_id=sid); print("VAULT load of tampered file: accepted (not detected on load)")
except Exception as e:
    print("VAULT load of tampered file: refused ->", type(e).__name__, str(e)[:80])

# ---- the history window
spine = object.__new__(core.PubPartnerSpine)
spine.vault = vault; spine.session_dir = tmp / "sessions"; spine.session_dir.mkdir()
def turn(i, provider="anthropic", ok=True, session="work1"):
    src = vault.store(user_id="synthetic", session_id=session, text=f"user turn {i} " + "u" * 1500)
    spine._append_turn("synthetic", session, {"fcp1": {"f": {"id": "alex"}, "proj": {"room": "pubpartner"}, "task": {}, "msg": {"text": "dup"}},
        "source": {"id": src.source_id}, "provider_result": {"ok": ok, "provider": provider},
        "friend_response": f"reply {i} " + "r" * 2000})
for i in range(1, 11): turn(i)
turn(11, provider="offline"); turn(12, ok=False)
h = spine._saved_private_history(user_id="synthetic", session_id="work1", friend_id="alex")
print(f"HISTORY given back after 12 exchanges in one session: {len(h)//2} exchanges; "
      f"user text kept {len(h[0]['content'])} of 1512 chars; reply kept {len(h[1]['content'])} of 2008 chars")
print("HISTORY which turns:", [x['content'][:12] for x in h if x['role']=='user'])
print("HISTORY in a NEW session of the same person:", spine._saved_private_history(user_id="synthetic", session_id="work2", friend_id="alex"))
print("HISTORY for a different friend in the same session:", len(spine._saved_private_history(user_id="synthetic", session_id="work1", friend_id="other")))
log = (spine.session_dir / "synthetic_work1_turns.jsonl")
row = json.loads(log.read_text().splitlines()[0])
print("TURN LOG keeps the full reply:", len(row["friend_response"]), "chars | user text in log:", row["fcp1"]["msg"].get("text_status"))
