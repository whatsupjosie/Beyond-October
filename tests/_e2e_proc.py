"""Helper run in a *separate process* by test_restart_persistence_e2e.py.

Boots the real ``main.app`` through its real lifespan against a given data
directory, performs the requested phase over HTTP routes, prints one JSON line.
The provider is the explicit deterministic ``mock`` adapter: no real model runs.
"""
import json, os, sys

root, datadir, phase = sys.argv[1], sys.argv[2], sys.argv[3]
os.environ["PUBCAST_DATA_DIR"] = datadir
for extra in ("", "/modules/wired", "/pubpartner", "/modules"):
    sys.path.insert(0, root + extra)
os.chdir(root)

from starlette.testclient import TestClient  # noqa: E402
import main  # noqa: E402

LIVE = "/api/pubpartner/turns/live"


def turn(client, message, session):
    r = client.post(LIVE, json={"message": message, "session_id": session, "friend": "alex",
                                "provider": {"provider": "mock"}})
    return r.status_code, r.json()


out = {}
with TestClient(main.app) as c:
    out["health"] = c.get("/api/health").status_code
    if phase == "write":
        for i, text in enumerate((
            "My red notebook is named Atlas Seven.",
            "ugh this stupid build keeps crashing again, I hate this compiler",
            "Remember that my sister's name is Marguerite.",
        )):
            status, body = turn(c, text, "first-run")
            out[f"turn{i}"] = {
                "status": status,
                "ok": body.get("ok"),
                "alex_source": (body.get("alex_bridge") or {}).get("analysis_source"),
                "alex_state": (body.get("alex_bridge") or {}).get("alex_state"),
                "receipt_ok": (body.get("receipt_chain") or {}).get("ok"),
            }
    elif phase == "recall":
        status, body = turn(c, "What is my red notebook called?", "second-run")
        memories = body.get("fcp1", {}).get("m") or body.get("fcp1", {}).get("memories") or []
        out["recall"] = {
            "status": status,
            "ok": body.get("ok"),
            "memory_texts": [m.get("txt") or m.get("text") for m in memories],
            "alex_source": (body.get("alex_bridge") or {}).get("analysis_source"),
        }
    else:
        raise SystemExit("unknown phase")
print("E2E_RESULT " + json.dumps(out, default=str))
