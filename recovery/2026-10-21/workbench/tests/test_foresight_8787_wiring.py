"""Current Foresight contract: one origin and single authoritative managers."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FORESIGHT = ROOT / 'static' / 'foresight.html'
CHAT = ROOT / 'static' / 'pub_partner_chat.html'
BACKEND = ROOT / '2i-backend' / 'server.js'
MAIN = ROOT / 'main.py'


def test_foresight_preserves_portals_and_uses_one_origin():
    text = FORESIGHT.read_text(encoding='utf-8')
    assert "pubpartnerStatusPath: '/api/pubpartner/status'" in text
    assert "twoIBase: '/api/foresight/bridge'" in text
    assert "twoIUi: '/writers-room'" in text
    assert "url:()=>CONFIG.twoIUi" in text
    assert "url:'/pub-partner-chat'" in text
    assert "url:'/pubpartner'" in text
    assert "url:'/static/foresight_care.html'" in text
    assert "checkDot('dot-2i', CONFIG.twoIBase + '/health')" in text
    assert "http://localhost:8787" not in text


def test_reach_keeps_one_writer_and_pubpartner_authority():
    text = MAIN.read_text(encoding='utf-8')
    assert '@app.get("/writers-room", include_in_schema=False)' in text
    assert 'Path(__file__).resolve().parent / "2i" / "writers-room-v22.html"' in text
    assert 'app.include_router(create_foresight_gateway(lambda: bot_manager, lambda: hub))' in text
    routes = (ROOT / 'modules' / 'pubpartner_routes.py').read_text(encoding='utf-8')
    assert 'router = APIRouter(prefix="/api/pubpartner"' in routes
    assert '@router.get("/status")' in routes


def test_pubpartner_character_chat_uses_same_origin_gateway():
    text = CHAT.read_text(encoding='utf-8')
    assert "const BRIDGE_BASE='/api/foresight/bridge'" in text
    assert '`${BRIDGE_BASE}/api/chat/characters`' in text
    assert '`${BRIDGE_BASE}/api/chat/character`' in text
    assert 'character_id:charId' in text
    assert "fetch('/api/bots')" not in text
    assert 'http://localhost:8787' not in text


def test_optional_original_2i_is_loopback_only_and_lifecycle_owned():
    text = BACKEND.read_text(encoding='utf-8')
    assert "app.get('/health'" in text
    assert "app.get('/api/chat/characters'" in text
    assert "app.post('/api/chat/character'" in text
    assert "process.env.HOST || '127.0.0.1'" in text
    starter = (ROOT / 'run_reach.py').read_text(encoding='utf-8')
    assert 'sidecar.start()' in starter
    assert 'sidecar.stop()' in starter
    assert "PUBCAST_SIDECAR_ONLY='1'" in (ROOT / 'modules' / 'foresight_sidecar.py').read_text()
    assert "process.env.PUBCAST_SIDECAR_ONLY === '1'" in text
    assert "choices=(\"foresight\", \"foresight-legacy\", \"writers-room\", \"lobby\")" in starter


def test_backend_script_parses():
    output = subprocess.run(['node', '--check', str(BACKEND)], capture_output=True, text=True)
    assert output.returncode == 0, output.stderr
