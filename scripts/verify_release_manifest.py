#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()
def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('root',nargs='?',default=str(Path(__file__).resolve().parents[1])); args=ap.parse_args()
    root=Path(args.root).resolve(); manifest=json.loads((root/'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
    errors=[]; listed={row['path']:row for row in manifest.get('files',[])}
    exclusions=set(manifest.get('manifest_exclusions',[]))
    actual={p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file() and p.relative_to(root).as_posix() not in exclusions}
    for rel,row in listed.items():
        p=actual.get(rel)
        if p is None: errors.append(f'missing: {rel}'); continue
        if p.stat().st_size!=row['size']: errors.append(f'size: {rel}')
        if sha256(p)!=row['sha256']: errors.append(f'hash: {rel}')
    for rel in sorted(set(actual)-set(listed)): errors.append(f'unlisted: {rel}')
    for rel in sorted(set(listed)-set(actual)): errors.append(f'listed_missing: {rel}')
    result={'ok':not errors,'listed_file_count':len(listed),'actual_file_count':len(actual),'errors':errors}
    print(json.dumps(result,indent=2)); return 0 if not errors else 1
if __name__=='__main__': raise SystemExit(main())
