"""Real PubCast process with temporary data and verified test-account identity."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='session')
def browser_type_launch_args(browser_type_launch_args):
    options = {**browser_type_launch_args, 'args': ['--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
    executable = os.environ.get('PLAYWRIGHT_CHROMIUM_EXECUTABLE')
    if executable:
        options['executable_path'] = executable
    return options


@pytest.fixture(scope='session')
def live_host(tmp_path_factory):
    directory = tmp_path_factory.mktemp('primp-host')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    env = dict(os.environ, PUBCAST_DATA_DIR=str(directory/'data'), PUBCAST_ENFORCE_AUTH='1', PUBCAST_JWT_SECRET=secrets.token_urlsafe(48))
    command = [sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', str(port), '--log-level', 'warning']
    with (directory/'host.log').open('w+') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)

        def healthy():
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError('Host exited:\n'+(directory/'host.log').read_text())
                try:
                    with urllib.request.urlopen(url+'/health', timeout=1) as response:
                        if response.status == 200:
                            return
                except OSError:
                    time.sleep(.1)
            raise RuntimeError('Host startup timeout:\n'+(directory/'host.log').read_text())

        def stop():
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

        def restart():
            nonlocal process
            stop()
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            healthy()

        try:
            healthy()
            password = 'Primp-'+secrets.token_urlsafe(24)+'-7!'
            request = urllib.request.Request(url+'/api/auth/setup', data=json.dumps({'username':'primp-browser', 'password':password, 'confirm_password':password}).encode(), headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request) as response:
                assert response.status == 201
                account = json.load(response)
            yield {'url':url, 'account':account, 'restart':restart}
        finally:
            stop()


@pytest.fixture
def mirror(page, context, live_host, tmp_path):
    context.add_init_script('sessionStorage.setItem("pubcast_token",'+json.dumps(live_host['account']['access_token'])+');')
    # Test the supported download-only path. This is not an OS save-picker test.
    context.add_init_script('window.showSaveFilePicker=undefined;')
    errors, console, requests = [], [], []
    page.on('pageerror', lambda error:errors.append(str(error)))
    page.on('console', lambda message:console.append({'type':message.type, 'text':message.text}))
    page.on('requestfailed', lambda request:requests.append({'url':request.url, 'failure':request.failure}))
    page.on('dialog', lambda dialog:dialog.accept())
    page.goto(live_host['url']+'/static/primp.html')
    page.wait_for_function('document.querySelector("#viewport canvas") && !document.querySelector("[data-base=sheila]").disabled')
    page.wait_for_function('!document.querySelector("#storage-status").textContent.includes("Checking")')
    yield page
    (tmp_path/'browser-log.json').write_text(json.dumps({'page_errors':errors, 'console':console, 'failed_requests':requests}, indent=2))
    assert not errors, errors
    assert not requests, requests
