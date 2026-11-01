"""Lifecycle owner for *optional* original Node 2i utilities.

The Foresight character and manuscript APIs run on Reach without Node. The
existing 2i Express service retains its unique thesaurus/model-proxy/legacy
commit/message utilities, hosted exclusively on loopback and proxied by Reach.
One run_reach.py launch supervises both processes when dependencies are present.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen


class Legacy2iService:
    def __init__(self, root: Path, data_dir: Path, reach_port: int,
                 *, install: bool = False):
        self.root = Path(root)
        self.project = self.root / '2i-backend'
        self.data_dir = Path(data_dir)
        self.reach_port = reach_port
        self.install = install
        self.process = None
        self.log = None
        self.url = None

    def start(self) -> bool:
        node = shutil.which('node')
        npm = shutil.which('npm')
        if not node or not (self.project / 'server.js').is_file():
            print('[2i] Node runtime absent; Reach characters, manuscripts and Foresight still work.')
            return False
        if not (self.project / 'node_modules' / 'express').is_dir():
            if not npm or not self.install:
                print('[2i] Optional Express dependencies missing (run npm ci in 2i-backend).')
                return False
            print('[2i] Installing optional 2i utility dependencies (first run only)...', flush=True)
            try:
                subprocess.run([npm, 'ci', '--omit=dev', '--ignore-scripts', '--no-audit', '--no-fund'],
                               cwd=self.project, check=True, timeout=75,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError) as error:
                print(f'[2i] Optional utility install unavailable: {type(error).__name__}; primary Foresight remains usable.')
                return False
        # Never assume 8787 is our own service. An ephemeral port is held only
        # briefly and never exposed to the browser or LAN.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        log_dir = self.data_dir / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log = (log_dir / 'legacy_2i.log').open('a', encoding='utf-8')
        env = dict(os.environ, PORT=str(port), HOST='127.0.0.1',
                   PUBCAST_URL=f'http://127.0.0.1:{self.reach_port}',
                   NODE_ENV='production', PUBCAST_SIDECAR_ONLY='1')
        try:
            self.process = subprocess.Popen([node, 'server.js'], cwd=self.project,
                                            env=env, stdout=self.log, stderr=subprocess.STDOUT)
            self.url = f'http://127.0.0.1:{port}'
            for _ in range(35):
                if self.process.poll() is not None:
                    break
                try:
                    with urlopen(self.url + '/health', timeout=0.2) as reply:
                        if reply.status == 200:
                            os.environ['PUBCAST_2I_BRIDGE_URL'] = self.url
                            print('[2i] Optional utilities connected through Foresight.')
                            return True
                except (OSError, TimeoutError):
                    time.sleep(0.1)
            print('[2i] Optional 2i service did not pass health check; continuing without it.')
            self.stop()
        except OSError as error:
            print(f'[2i] Optional utilities unavailable: {error}')
            self.stop()
        return False

    def stop(self) -> None:
        os.environ.pop('PUBCAST_2I_BRIDGE_URL', None)
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=4)
            self.process = None
        if self.log is not None:
            self.log.close()
            self.log = None
