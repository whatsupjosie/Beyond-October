import json, sys, time, subprocess, os, urllib.request, urllib.error
REPO, DATA, PORT = sys.argv[1], sys.argv[2], sys.argv[3]
B = f"http://127.0.0.1:{PORT}"
env = dict(os.environ, PUBCAST_OWNER_PASSWORD="Trace-Owner-Pass-2026!", PUBCAST_OWNER_USERNAME="owner")
for k in list(env):
    if k.lower() in ("http_proxy","https_proxy","all_proxy"): env.pop(k)
def start():
    log = open(DATA + ".log", "ab")
    p = subprocess.Popen([sys.executable, "run_reach.py", "--no-browser", "--port", PORT, "--data-dir", DATA, "--no-legacy-2i"], cwd=REPO, env=env, stdout=log, stderr=log)
    for _ in range(90):
        try:
            urllib.request.urlopen(B + "/health", timeout=2); return p
        except Exception: time.sleep(1)
    raise SystemExit("boot timeout")
tok = None
def call(m, path, body=None):
    req = urllib.request.Request(B + path, method=m, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("content-type", "application/json")
    if tok: req.add_header("authorization", "Bearer " + tok)
    try:
        r = urllib.request.urlopen(req, timeout=60); return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]
def show(label, res, n=900):
    print(f"## {label}: {res[0]}\n{json.dumps(res[1], default=str)[:n]}\n")
p = start()
try:
    s, r = call("POST", "/api/auth/login", {"username": "owner", "password": env["PUBCAST_OWNER_PASSWORD"]})
    show("login", (s, {k: (v if k != "access_token" else "<token>") for k, v in r.items()} if isinstance(r, dict) else r))
    tok = r.get("access_token") if isinstance(r, dict) else None
    show("care/status", call("GET", "/api/alex/care/status"))
    show("care/observe (EQ reading+evidence)", call("POST", "/api/alex/care/observe", {"kind": "tone_shift", "observed": {"typing": "short fragments", "words": "tired"}, "hypothesis": "user may be worn down", "alternatives": ["just busy"]}))
    show("alex/message #1", call("POST", "/api/alex/message", {"message": "I'm exhausted and I feel like nobody is listening to me today.", "typing_speed": 20}), 1500)
    show("alex/state", call("GET", "/api/alex/state"))
    show("packet after msg", call("GET", "/api/alex-jeremy/packet?session_id=default"), 1500)
    show("jeremy signal (authority)", call("POST", "/api/alex-jeremy/signal", {"session_id": "default", "room_state": "tense", "urgency": "high", "reason": "guest escalation", "payload": {"requested_action": "mute_guest"}}), 1800)
    show("alex/message #2 correction", call("POST", "/api/alex/message", {"message": "No, you misread me. I'm not upset, I'm just tired. Please don't treat me as fragile.", "typing_speed": 60}), 1500)
    show("alex/state after correction", call("GET", "/api/alex/state"))
    show("packet after correction", call("GET", "/api/alex-jeremy/packet?session_id=default"), 1500)
    show("memory/recent", call("GET", "/api/alex/memory/recent?limit=5"), 1200)
    show("care/events", call("GET", "/api/alex/care/events"), 800)
    show("blackbox status", call("GET", "/api/operator/blackbox/status"))
    show("blackbox verify", call("GET", "/api/operator/blackbox/verify"))
finally:
    p.terminate(); p.wait(20)
print("==== RESTART ====")
p = start()
try:
    s, r = call("POST", "/api/auth/login", {"username": "owner", "password": env["PUBCAST_OWNER_PASSWORD"]}); tok = r.get("access_token")
    show("alex/state after restart", call("GET", "/api/alex/state"))
    show("packet after restart", call("GET", "/api/alex-jeremy/packet?session_id=default"), 1500)
    show("memory/recent after restart", call("GET", "/api/alex/memory/recent?limit=5"), 1200)
    show("care/events after restart", call("GET", "/api/alex/care/events"), 500)
finally:
    p.terminate(); p.wait(20)
