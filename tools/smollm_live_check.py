import subprocess, urllib.request, urllib.error, json, time, tempfile, secrets, signal, os, sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
import argparse, datetime
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=Path('smollm-check-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S')))
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
os.chdir(args.output)
test_data = tempfile.TemporaryDirectory(prefix='pubcast-smollm-check-')
log = open('live-integration.log', 'w')
p = subprocess.Popen([sys.executable, str(root/'run_smollm.py'), '--port', '8100', '--model-port', '8101', '--data-dir', test_data.name, '--no-browser'], stdout=log, stderr=log, **({'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP} if os.name=='nt' else {'start_new_session':True}))
def req(path, data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token: headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request('http://127.0.0.1:8100'+path, data=None if data is None else json.dumps(data).encode(), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=200) as response: return response.status, json.load(response)
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read())
results = {'tests': []}
try:
    for i in range(300):
        if p.poll() is not None: raise RuntimeError('Launcher exited: inspect log')
        try:
            status, body = req('/api/auth/status')
            if status == 200: break
        except OSError: pass
        time.sleep(.5)
    else: raise RuntimeError('Reach not ready')
    password = secrets.token_urlsafe(22) + '1!Aa'
    status, auth = req('/api/auth/setup', {'username': 'smol_test_owner', 'password': password, 'confirm_password': password})
    assert status == 201, (status, auth)
    token = auth['access_token']
    status, config = req('/api/pubpartner/providers/local-config', token=token)
    assert status == 200 and config['enabled'], (status, config)
    results = {'config': config, 'tests': []}
    import hashlib
    with urllib.request.urlopen('http://127.0.0.1:8100/static/pubpartner.js') as response:
        assert hashlib.sha256(response.read()).digest() == hashlib.sha256((root/'static/pubpartner.js').read_bytes()).digest()
    results['served_browser_script'] = 'matches audited file'
    assert req('/api/pubpartner/providers/local-config')[0] == 401
    results['anonymous_config_status'] = 401
    for message in ['Hello. Please say hello back briefly.', 'What is two plus three? Answer briefly.']:
        t = time.monotonic()
        status, reply = req('/api/pubpartner/turns/live', {'session_id':'smollm-live-check', 'message':message, 'friend':'alex', 'allow_fallback':False}, token)
        result = {'status':status, 'elapsed_seconds':round(time.monotonic()-t,2), 'message':message, 'reply':reply.get('reply'), 'provider_result':reply.get('provider_result'), 'receipt':reply.get('receipt'), 'fallback':reply.get('provider_fallback')}
        Path('last-live-response.json').write_text(json.dumps(reply, indent=2))
        results['tests'].append(result)
        Path('live-integration-results.json').write_text(json.dumps(results, indent=2))
        print(json.dumps(result), flush=True)
        assert status == 200 and reply.get('ok'), 'Live turn failed; inspect evidence'
        assert reply['provider_result']['usage']['finish_reason'] == 'stop'
        assert reply['provider_result']['usage']['prompt_adapter'] == 'smollm_chat_v2'
        assert not reply.get('provider_fallback')
        assert '@FCP1' not in reply['reply'] and 'FCP1_VERBATIM' not in reply['reply']
        assert reply['reply'].strip().lower() != message.strip().lower(), 'Model echoed the request; semantic check failed'
        if 'two plus three' in message: assert 'five' in reply['reply'].lower() or '5' in reply['reply']
    status, continuity = req('/api/pubpartner/turns/live', {'session_id':'continuity-check', 'message':'What color is my notebook? Answer with the color only.', 'history':[{'role':'user','content':'My notebook is blue.'},{'role':'assistant','content':'Understood.'}], 'friend':'alex', 'allow_fallback':False}, token)
    assert status == 200 and 'blue' in continuity.get('reply','').lower(), continuity
    results['continuity'] = {'status':status,'reply':continuity['reply']}
    status, oversized = req('/api/pubpartner/turns/live', {'session_id':'oversize-check', 'message':'天地玄黄宇宙洪荒'*4000, 'prompt_mode':'full', 'friend':'alex','allow_fallback':False}, token)
    assert status == 503 and not oversized.get('ok')
    results['oversize'] = {'status':status,'error':oversized['provider_result']['error']}
    status, writers = req('/api/writers-room/config', token=token)
    assert status == 200 and writers['provider']['model'] == 'smollm2'
    results['writers_room'] = {'status':status, 'response':writers}
    status, prose = req('/api/pubpartner/manuscript/generate', {'project_id':'smol-test','context_lines':['The door opened onto an empty stage.'],'instruction':'Add one short sentence.'}, token)
    results['manuscript'] = {'status':status, 'response':prose}
    Path('live-integration-results.json').write_text(json.dumps(results, indent=2))
    print('MANUSCRIPT', status, prose, flush=True)
    assert status == 200 and prose.get('lines')
    assert len(' '.join(prose['lines'])) > 10
    assert not any('FCP1' in line or 'Return only new prose' in line for line in prose['lines'])
finally:
    if p.poll() is None:
        p.send_signal(signal.CTRL_BREAK_EVENT) if os.name == 'nt' else p.terminate()
        try: p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            import psutil
            for child in psutil.Process(p.pid).children(recursive=True):
                try: child.kill()
                except psutil.NoSuchProcess: pass
            p.kill(); p.wait(); raise AssertionError('Supervisor failed to stop children')
    import socket
    for port in (8100,8101):
        with socket.socket() as probe:
            assert probe.connect_ex(('127.0.0.1',port)) != 0, 'Child server leaked after supervisor shutdown'
    results['supervisor_shutdown'] = 'SIGTERM stopped both services; both ports closed'
    Path('live-integration-results.json').write_text(json.dumps(results, indent=2))

    log.close()
    test_data.cleanup()
