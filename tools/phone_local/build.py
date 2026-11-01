from pathlib import Path
import argparse,base64,json,re,hashlib

parser=argparse.ArgumentParser(description='Build the self-contained local phone writing desk')
parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
parser.add_argument('--output-dir',type=Path,default=Path('dist'))
parser.add_argument('--inline-output',type=Path)
args=parser.parse_args()
BASE=args.output_dir.resolve();BASE.mkdir(parents=True,exist_ok=True)
ROOT=args.root.resolve()
HERE=Path(__file__).parent
html=(ROOT/'2i/index.html').read_text()
art=(ROOT/'2i/2i-assets/writers-room-art.webp').read_bytes()
assert hashlib.sha256(art).hexdigest()=='495970f71a5615c947e73e1f32c0e56906037d4099a19152a19abba1e9134de7'
css=re.search(r'<style>(.*?)</style>',html,re.S)[1]
css=re.sub(r"@import url\(.*?\);",'',css)
for name in ['reach.css','artwork.css','phone.css','reader.css']:
    css+='\n'+(ROOT/'2i/2i-assets'/name).read_text()
data='data:image/webp;base64,'+base64.b64encode(art).decode()
css=':root { --reach-original-art:url("'+data+'"); }\n'+css.replace("url('writers-room-art.webp')",'var(--reach-original-art)')
body=re.search(r'<body[^>]*>(.*?)<script>',html,re.S)[1]
base_script=re.search(r'<script>(.*?)</script>',html,re.S)[1]
reach=(ROOT/'2i/2i-assets/reach.js').read_text()
reach=reach.replace("const networked = location.protocol === 'http:' || location.protocol === 'https:';","const networked = false;")
reach=reach.replace("if(!window.indexedDB || (networked && !serverReady))return Promise.resolve(null);","return Promise.resolve(null); // Local copies use browser storage; no IndexedDB requirement.")
artwork=(ROOT/'2i/2i-assets/artwork.js').read_text()
start=artwork.index('window.reachArtworkReady=fetch(')
end=artwork.index('\nrefreshArtwork();',start)
mapping=json.loads((ROOT/'2i/2i-assets/hotspots.json').read_text())
artwork=artwork[:start]+'window.reachArtworkReady=Promise.resolve('+json.dumps(mapping,ensure_ascii=False)+').then(applyHotspotMap);'+artwork[end:]
phone=(ROOT/'2i/2i-assets/phone.js').read_text()
phone=phone.replace("const url=new URL(location.href);url.searchParams.set('view',value);history.replaceState(null,'',url);","try {const url=new URL(location.href);url.searchParams.set('view',value);history.replaceState(null,'',url);} catch (_) {}")
scripts=[]
for script in [base_script,(ROOT/'2i/2i-assets/button-bindings.js').read_text(),reach,artwork,phone,(ROOT/'2i/2i-assets/reader.js').read_text()]:
    script=re.sub(r'\blocalStorage\b','reachPhoneStore',script)
    script=re.sub(r'\bsessionStorage\b','reachPhoneSession',script)
    script=re.sub(r'\bfetch\s*\(','offlineNoNetwork(',script)
    scripts.append(script)
scripts.insert(0,(HERE/'bootstrap.js').read_text())
scripts.append((HERE/'local.js').read_text())
scripts.append(re.sub(r'\blocalStorage\b','reachPhoneStore',(ROOT/'2i/2i-assets/desk-controls.js').read_text()))
parts='\n'.join('<script>\n'+s+'\n</script>' for s in scripts)
fragment='<div id="reach-phone-inline">\n<style>\n'+css+'\n'+(HERE/'inline.css').read_text()+'\n</style>\n'+body+'\n</div>\n'+parts+'\n<script>\nconst phonePreviewRoot=document.getElementById("reach-phone-inline");\nphonePreviewRoot.setAttribute("aria-label","Reach phone writing desk");\n</script>\n'
assert len(fragment.encode())<1000000
assert not re.search(r'\bfetch\s*\(|new\s+(?:WebSocket|XMLHttpRequest)\b',fragment)
assert not re.search(r'<(?:html|head|body)\b|<!doctype',fragment,re.I)
if args.inline_output:
    args.inline_output.parent.mkdir(parents=True,exist_ok=True)
    args.inline_output.write_text(fragment)
standalone='<!doctype html>\n<html lang="en" data-reach-artwork="original"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Reach · Phone writing desk</title><style>\n'+css+'\n</style></head><body>\n'+body+'\n'+parts+'\n</body></html>\n'
(BASE/'Reach_Phone_Standalone.html').write_text(standalone)
print(json.dumps({'inline_bytes':len(fragment.encode()),'standalone_bytes':len(standalone.encode()),'external_dependencies':0,'live_model_connected':False,'original_image_sha256':hashlib.sha256(art).hexdigest()},indent=2))
