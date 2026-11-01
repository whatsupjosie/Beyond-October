from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

PORTAL_PAGES = [
    "foresight.html", "general_chat.html", "world_chat.html", "stage.html", "stage_panoramic.html",
    "control_room.html", "studio_control_room.html", "director_switcher.html",
    "world.html", "pubworld_stage.html", "bar.html", "dressing.html",
    "waiting_room.html", "map.html", "pubcast_teleprompter.html", "gallery.html",
    "analytics.html", "doctor.html", "pub_partner_chat.html", "pubpartner.html",
]


def test_launcher_defaults_to_foresight_but_keeps_writers_room_override():
    text = (ROOT / "run_reach.py").read_text(encoding="utf-8")
    assert 'choices=("foresight", "foresight-legacy", "writers-room", "lobby")' in text
    assert 'default="foresight"' in text
    assert 'start_path = {"foresight": "/foresight-counter", "foresight-legacy": "/foresight", "writers-room": "/writers-room", "lobby": "/"}[args.start_page]' in text
    assert 'os.environ["PUBCAST_PORT"] = str(args.port)' in text


def test_reach_exposes_foresight_counter_and_login_routes():
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert '@app.get("/foresight", include_in_schema=False)' in text
    assert '@app.get("/counter", include_in_schema=False)' in text
    assert 'return _page("foresight.html", request)' in text
    assert '@app.get("/login", include_in_schema=False)' in text
    assert 'return _page("login.html", request)' in text


def test_foresight_uses_canonical_absolute_portal_targets_and_auth_boot():
    text = (STATIC / "foresight.html").read_text(encoding="utf-8")
    assert '<script src="/static/reach_auth.js"></script>' in text
    assert '<script src="/static/foresight.config.js"></script>' in text
    assert "url:'/static/world_chat.html'" in text
    assert "url:'/pub-partner-chat'" in text
    assert "twoIUi: '/writers-room'" in text
    assert "await window.ReachAuth.requireSession('/foresight')" in text
    assert "refreshDots();\n  setInterval(refreshDots, 6000);" in text
    assert "url:'general_chat.html" not in text


def test_neighbor_portals_share_the_reach_auth_adapter():
    missing = []
    for name in PORTAL_PAGES:
        text = (STATIC / name).read_text(encoding="utf-8")
        if '<script src="/static/reach_auth.js"></script>' not in text:
            missing.append(name)
    assert not missing, f"missing auth adapter: {missing}"
    assert '<script src="/static/reach_auth.js"></script>' in (ROOT / "2i" / "index.html").read_text(encoding="utf-8")


def test_login_uses_real_first_run_setup_and_safe_same_origin_return():
    text = (STATIC / "login.html").read_text(encoding="utf-8")
    assert "fetch('/api/auth/setup'" in text
    assert "confirm_password:confirm" in text
    assert "window.ReachAuth.saveSession(data)" in text
    assert "target.origin !== location.origin" in text
    assert "Initial owner setup has already been completed." in text


def test_shared_auth_client_only_decorates_same_origin_fetches(tmp_path):
    client = STATIC / "reach_auth.js"
    harness = tmp_path / "auth_harness.js"
    harness.write_text(rf'''
const fs=require('fs'); const vm=require('vm');
const mem=()=>{{const d=new Map();return {{getItem:k=>d.has(k)?d.get(k):null,setItem:(k,v)=>d.set(k,String(v)),removeItem:k=>d.delete(k)}}}};
global.window=global; global.top=global;
global.sessionStorage=mem(); global.localStorage=mem();
global.location={{origin:'http://127.0.0.1:8000',href:'http://127.0.0.1:8000/static/bar.html',pathname:'/static/bar.html',search:'',hash:'',assign:u=>{{global.redirect=u;}}}};
const calls=[];
global.fetch=async (input,init)=>{{calls.push({{url:typeof input==='string'?input:input.url,headers:Object.fromEntries(new Headers(init?.headers || (input instanceof Request?input.headers:{{}})).entries())}});return new Response('{{"ok":true}}',{{status:200,headers:{{'content-type':'application/json'}}}});}};
vm.runInThisContext(fs.readFileSync({str(client)!r},'utf8'),{{filename:'reach_auth.js'}});
sessionStorage.setItem('pubcast_token','abc123'); sessionStorage.setItem('pubcast_user',JSON.stringify({{username:'alice',role:'owner'}}));
(async()=>{{
 await fetch('/api/state/user',{{headers:{{'X-Client-Id':'stale','X-Dev-Role':'guest'}}}});
 await fetch('http://localhost:8787/health',{{headers:{{'X-Dev-Role':'guest'}}}});
 sessionStorage.removeItem('pubcast_token'); sessionStorage.removeItem('pubcast_user');
 await fetch('/api/dev-only',{{headers:{{'X-Client-Id':'legacy-user','X-Dev-Role':'mod'}}}});
 const a=calls[0], b=calls[1], c=calls[2];
 if(a.headers.authorization!=='Bearer abc123') throw new Error('same-origin bearer missing');
 if(a.headers['x-client-id']!=='alice') throw new Error('client id not rebound');
 if('x-dev-role' in a.headers) throw new Error('legacy role leaked');
 if('authorization' in b.headers) throw new Error('cross-origin bearer leaked');
 if(c.headers['x-dev-role']!=='mod' || c.headers['x-client-id']!=='legacy-user') throw new Error('relaxed-mode legacy headers were altered');
 console.log('ok');
}})().catch(e=>{{console.error(e);process.exit(1)}});
''', encoding="utf-8")
    run = subprocess.run(["node", str(harness)], capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    assert "ok" in run.stdout


def test_changed_javascript_parses():
    for source in [STATIC / "reach_auth.js", ROOT / "2i-backend" / "server.js"]:
        run = subprocess.run(["node", "--check", str(source)], capture_output=True, text=True, check=False)
        assert run.returncode == 0, run.stderr
