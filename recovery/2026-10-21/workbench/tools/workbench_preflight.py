#!/usr/bin/env python3
"""Offline, read-only PubCast/Foresight workbench preflight.

Checks the actual Reach app without starting a public server or opening a browser.
Returns nonzero on missing critical assets/routes and prints a usable diagnosis.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    problems: list[str] = []
    def check(label: str, ok: bool, detail: str = '') -> None:
        print(('PASS' if ok else 'FAIL') + '  ' + label + (': ' + detail if detail else ''), flush=True)
        if not ok:
            problems.append(label + (': ' + detail if detail else ''))

    for relative in ('run_reach.py', 'start_reach.py', 'main.py', 'static/foresight_counter.html',
                     'static/foresight_counter.js', 'static/foresight_programs.js',
                     'static/foresight_shapes.js', 'static/foresight_chain.js',
                     'static/foresight_gl.js', 'static/reach_auth.js'):
        check('Packaged ' + relative, (ROOT / relative).is_file())
    for name in ('pete', 'jeremy', 'repeat', 'sir_purfluous'):
        check('First-run bot config ' + name, (ROOT / 'data' / 'bots' / (name + '.json')).is_file())
    if problems:
        print('\nPRE-FLIGHT FAILED: missing packaged files; no server was started.')
        return 1

    from fastapi.testclient import TestClient
    from main import app
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            for route, marker in (('/foresight-counter', 'foresight_counter.js'),
                                  ('/writers-room', 'reach_auth.js'),
                                  ('/pubpartner', 'reach_auth.js'),
                                  ('/pub-partner-chat', None)):
                r = client.get(route)
                check('Reach page ' + route, r.status_code == 200 and (marker is None or marker in r.text),
                      'HTTP ' + str(r.status_code))
            html = (ROOT / 'static' / 'foresight_counter.html').read_text(encoding='utf-8')
            for asset in sorted(set(re.findall(r'<script[^>]+src="(/static/[^\"]+)"', html))):
                r = client.get(asset)
                check('Counter asset ' + asset, r.status_code == 200, 'HTTP ' + str(r.status_code))
            # A served editor page is not usable if its Reach runtime is absent.
            writer = client.get('/writers-room').text
            check('2i loads Reach persistence and conversation runtime',
                  '<script src="/2i-assets/reach.js"></script>' in writer)
            check('2i loads Reach writing-desk styles',
                  '/2i-assets/reach.css' in writer)
            for element in ('shelfBtn', 'partnerSelect', 'partnerNote', 'reachProvider',
                            'reachModel', 'reachCredential', 'reachBaseURL'):
                check('2i runtime control ' + element, 'id="' + element + '"' in writer)
            for asset in ('/2i-assets/reach.js', '/2i-assets/reach.css'):
                response = client.get(asset)
                check('2i runtime asset ' + asset, response.status_code == 200,
                      'HTTP ' + str(response.status_code))
            registry = (ROOT / 'static' / 'foresight_programs.js').read_text(encoding='utf-8')
            for pid, target in (('twoi', '/writers-room'), ('pubpartner_workspace', '/pubpartner'),
                                ('pubpartner_chat', '/pub-partner-chat')):
                check('Picker registration ' + pid, "id: '" + pid + "'" in registry and target in registry)
            check('Empty Counter on new session', "counter.open('world_chat')" not in html)
    except Exception as error:
        check('Reach startup', False, type(error).__name__ + ': ' + str(error))
    print('\n' + ('PREFLIGHT PASS: packaged routes and assets respond. Interactive use still needs a browser test.'
                    if not problems else 'PREFLIGHT FAILED: ' + str(len(problems)) + ' check(s) need repair.'))
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
