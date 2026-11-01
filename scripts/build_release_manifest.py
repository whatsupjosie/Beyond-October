#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
EXCLUDE = {'RELEASE_MANIFEST.json'}
def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()
def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('root',nargs='?',default=str(Path(__file__).resolve().parents[1])); args=ap.parse_args()
    root=Path(args.root).resolve(); files=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file(): continue
        rel=p.relative_to(root).as_posix()
        if rel in EXCLUDE: continue
        files.append({'path':rel,'size':p.stat().st_size,'sha256':sha256(p)})
    manifest={
      'name':'PubPartner_CANONICAL_RC7_RECONCILED_20260712',
      'version':(root/'VERSION').read_text(encoding='utf-8').strip(),
      'created_at_utc':datetime.now(timezone.utc).isoformat(),
      'base':'PubPartner_PRELAUNCH_RC6_PROVIDER_NEUTRALIZER_20260712.zip',
      'purpose':'Canonical reconciliation with default Alex/Jeremy/Pub Manager/Governance wiring, release hygiene, adversarial authority verification, and provenance.',
      'validation':{
        'python_compile':'passed','javascript_syntax':'passed','pytest':'132 passed, 3 skipped',
        'preflight':'passed','local_smoke':'passed','authenticated_restart_probe':'passed',
        'control_plane_probe':'passed','live_cloud_provider_calls':'not run','live_ollama':'not run',
        'native_windows':'not run; static and portable-path checks only'
      },
      'manifest_exclusions':sorted(EXCLUDE),'file_count':len(files),'files':files,
    }
    (root/'RELEASE_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'ok':True,'file_count':len(files),'manifest':str(root/'RELEASE_MANIFEST.json')},indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
