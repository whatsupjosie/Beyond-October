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
PFX = sys.argv[4]

def brief(r):
    if not isinstance(r, dict): return r
    out = {}
    def walk(d, pre=""):
        for k, v in d.items():
            if isinstance(v, dict) and len(pre) < 40: walk(v, pre + k + ".")
            elif k in ("alex_state","user_battery","tone_guidance","fragility_level","care_priority","do_not_touch","analysis_source","analysis_error","jeremy_whisper","whisper","status","error","provider","model","response","reply","text","fallback","generated","bridge_scope","generated_at","adjudication","judgment","data_label","label","ok","detail","session_id"):
                out[pre + k] = v if not isinstance(v, str) else v[:260]
    walk(r); return out
p = start()
try:
    s_, r = call("POST", "/api/auth/login", {"username": "owner", "password": env["PUBCAST_OWNER_PASSWORD"]}); tok = r["access_token"]
    call("POST", PFX + "/sessions", {"session_id": "trace-pp"})
    call("POST", PFX + "/turns", {"session_id": "trace-pp", "message": "My sister Marigold-Zebra moved to Quillfeather Lane last spring."})
    for fb in (False, True):
        s_, r = call("POST", PFX + "/turns", {"session_id": "trace-pp", "message": "What do you remember about my sister?", "generate_response": True, "allow_fallback": fb})
        print("## generate allow_fallback=", fb, s_)
        for k in ("friend_response", "provider_fallback", "provider_result", "raw_response", "companion_review", "blackbox_started", "blackbox_committed", "provenance", "live_loop"):
            print("  ", k, "=", json.dumps(r.get(k), default=str)[:420] if isinstance(r, dict) else r)
        pt = r.get("llm_prompt_text", "") if isinstance(r, dict) else ""
        print("   prompt_len", len(pt), "contains_private_memory_marker", "Marigold-Zebra" in pt, "policy", json.dumps(r.get("prompt_policy"), default=str)[:300])
finally:
    p.terminate(); p.wait(20)
