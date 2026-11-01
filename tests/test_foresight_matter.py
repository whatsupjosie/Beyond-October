"""Foresight Matter: the C++ material renderer, its WebAssembly build and the page skin.

These checks keep the three layers in step: the C++ enums, the browser enums,
the compiled exports, and the Counter's wiring of frames, blades and bench.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


def _cpp_enum(name):
    src = (STATIC / "foresight_matter.cpp").read_text(encoding="utf-8")
    body = src.split(f"enum {name} : int {{", 1)[1].split("};", 1)[0]
    return {k: int(v) for k, v in re.findall(r"([A-Z_]+)\s*=\s*(\d+)", body)}


def _js_enum(name):
    src = (STATIC / "foresight_matter.js").read_text(encoding="utf-8")
    body = src.split(f"const {name} = {{", 1)[1].split("};", 1)[0]
    return {k: int(v) for k, v in re.findall(r"([A-Z_]+):(\d+)", body)}


def test_browser_enums_match_cpp():
    assert _js_enum("MAT") == _cpp_enum("Mat")
    assert _js_enum("SHAPE") == _cpp_enum("Shape")


def test_canonical_palette_present():
    mats = _cpp_enum("Mat")
    for name in ("PEARL", "GLASS_SAPPHIRE", "EMERALD_ENAMEL", "GLASS_AMETHYST", "OBSIDIAN_LACQUER", "COPPER", "BRONZE", "BRASS", "WALNUT"):
        assert name in mats, name


def test_wasm_is_built_and_exports_the_api():
    wasm = (STATIC / "foresight_matter.wasm").read_bytes()
    assert wasm[:4] == b"\0asm"
    for export in (b"fm_render_tray", b"fm_render_bench", b"fm_shape_distance", b"fm_set_light", b"fm_buffer"):
        assert export in wasm, export


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_wasm_renders_a_tray_with_a_hole():
    script = r"""
const fs=require('fs');
WebAssembly.instantiate(fs.readFileSync(process.argv[1]),{env:{}}).then(({instance})=>{
  const e=instance.exports, W=200, H=140;
  const rc=e.fm_render_tray(W,H,20,1, 80,50,6,0.12,0, 0,51, 14,8, 135,48, 0,0,3, -40,-20,40,20);
  const px=new Uint8Array(e.memory.buffer,e.fm_buffer(),W*H*4);
  const at=(x,y)=>px[4*(y*W+x)+3];
  console.log(JSON.stringify({rc, centre:at(100,70), rim:at(100,70-48), corner:at(1,1),
    outside:e.fm_shape_distance(1,80,50,6,0.12,0,95,0)>0, inside:e.fm_shape_distance(1,80,50,6,0.12,0,0,0)<0}));
});"""
    out = subprocess.run(["node", "-e", script, str(STATIC / "foresight_matter.wasm")], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["rc"] == 0
    assert r["centre"] == 0          # under the content: not drawn
    assert r["rim"] == 255           # the rim is opaque
    assert r["corner"] < 255         # outside the shape: only shadow
    assert r["outside"] and r["inside"]


def test_counter_page_uses_the_skin():
    html = (STATIC / "foresight.html").read_text(encoding="utf-8")
    assert '<script src="/static/foresight_matter.js"></script>' in html
    assert '<script src="/static/foresight_skin.js"></script>' in html
    assert '<canvas id="bench"' in html
    assert "window.ForesightSkin.attach(tray, saved)" in html
    assert "look:t.look" in html                                   # material choice survives a reload
    assert "skin.fanAngles(trays.length+1)" in html                 # radial deck: trays plus one blank blade
    assert "radial-ghost" in html                                    # closed blades fall from the pivot
    assert "Change tray material" in html


def test_skin_fits_frames_outward_only():
    js = (STATIC / "foresight_skin.js").read_text(encoding="utf-8")
    # the content rectangle must sit inside the frame by the full inset at every sample point
    assert "if(M.distance(s, x, y) > -INSET) return false;" in js
    assert "const hole = [" in js
