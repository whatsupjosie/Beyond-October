"""Launch an isolated authenticated studio through the managed preview runner."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=4173)
    parser.add_argument('--strictPort', action='store_true')
    args = parser.parse_args()
    data = Path(os.environ.get('PUBCAST_PREVIEW_DATA_DIR', str(ROOT / '.preview-owner-runtime'))).resolve()
    data.mkdir(parents=True, exist_ok=True)
    os.environ['PUBCAST_DATA_DIR'] = str(data)
    os.environ['PUBCAST_ENFORCE_AUTH'] = '1'
    os.environ['PUBCAST_PORT'] = str(args.port)
    from run_pubpartner import _persistent_secret
    from run_reach import _seed_packaged_bot_configs
    os.environ['PUBCAST_JWT_SECRET'] = _persistent_secret(data / 'secure' / 'jwt_secret.txt')
    _seed_packaged_bot_configs(ROOT, data)
    import uvicorn
    uvicorn.run('main:app', host=args.host, port=args.port)


if __name__ == '__main__':
    main()
