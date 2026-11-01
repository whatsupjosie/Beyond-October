import {build} from 'esbuild';
import {mkdir,copyFile,readdir,readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=path.dirname(fileURLToPath(import.meta.url));
const out=path.resolve(root,'../2i-assets/vendor/docx');
await mkdir(out,{recursive:true});
await build({entryPoints:[path.join(root,'engine-entry.js')],bundle:true,platform:'browser',format:'esm',outfile:path.join(out,'engine.js'),minify:true,legalComments:'eof'});
await copyFile(path.join(root,'node_modules/@docx-editor.dev/core/dist/harfbuzz.wasm'),path.join(out,'harfbuzz.wasm'));
await copyFile(path.join(root,'node_modules/@docx-editor.dev/core/dist/editor.css'),path.join(out,'editor.css'));
await mkdir(path.join(out,'fonts'),{recursive:true});
const fonts=path.join(root,'node_modules/@docx-editor.dev/fonts/assets');
for(const n of await readdir(fonts))if(/^(LiberationMono|LiberationSerif|Carlito)-/.test(n))await copyFile(path.join(fonts,n),path.join(out,'fonts',n));
const notices=[];
async function scan(folder){for(const e of await readdir(folder,{withFileTypes:true})){const p=path.join(folder,e.name);if(e.isDirectory()){if(e.name!=='.bin')await scan(p);}else if(/^(LICENSE|LICENCE|COPYING|NOTICE|THIRD_PARTY_NOTICES|OFL|LPPL|GUST)/i.test(e.name)||e.name==='license')notices.push('\n## '+path.relative(root,p)+'\n\n'+await readFile(p,'utf8'));}}
await scan(path.join(root,'node_modules'));
await writeFile(path.join(out,'THIRD_PARTY_NOTICES.md'),'# 2i offline editor and language-data notices\n'+notices.join('\n'));
console.log(JSON.stringify({engine:'2.32.0',output:out,remoteFonts:false}));
