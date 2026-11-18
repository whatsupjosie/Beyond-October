#!/usr/bin/env python3
"""Generate the 2i format-matrix fixtures in tests/fixtures/formats/ with real producers.

Documents come from LibreOffice (soffice) and pandoc, media from ffmpeg, images from Pillow, so the tests check
2i against files made by the applications writers actually use, not hand-built approximations. The fixtures are
committed; this script is only needed to regenerate them (Linux; needs soffice, pandoc, ffmpeg, Pillow).

    python tools/make_format_fixtures.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "formats"
TEXT = ["Beyond October fixture — first line", "Second line with café, naïve and résumé"]
SOFFICE_TARGETS = {
    # target extension: (source, LibreOffice filter)
    "docx": ("odt", "docx:MS Word 2007 XML"),
    "doc": ("odt", "doc:MS Word 97"),
    "rtf": ("odt", "rtf:Rich Text Format"),
    "pdf": ("odt", "pdf:writer_pdf_Export"),
    "odp": ("txt-slides", "odp"),
    "pptx": ("txt-slides", "pptx:Impress MS PowerPoint 2007 XML"),
    "ods": ("csv", "ods"),
    "xlsx": ("csv", "xlsx:Calc MS Excel 2007 XML"),
}


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(list(args), check=True, cwd=cwd, capture_output=True, timeout=300)


def main() -> int:
    for tool in ("soffice", "pandoc", "ffmpeg"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} is required to regenerate the fixtures")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        profile = "-env:UserInstallation=file://" + str(work / "lo-profile")
        (work / "sample.md").write_text("\n\n".join(TEXT) + "\n", encoding="utf-8")
        run("pandoc", "sample.md", "-o", "sample.odt", cwd=work)
        run("pandoc", "sample.md", "--metadata", "title=Beyond October fixture", "-o", str(OUT / "sample.epub"), cwd=work)
        (work / "slides.md").write_text("# Beyond October fixture\n\n" + TEXT[1] + "\n", encoding="utf-8")
        run("pandoc", "slides.md", "-o", "slides.pptx", cwd=work)  # pandoc writes PPTX natively, not ODP
        (work / "sample.csv").write_text("Name,Note\nfixture,café\nsecond,naïve\n", encoding="utf-8")
        for target, (source, flt) in SOFFICE_TARGETS.items():
            src = {"odt": "sample.odt", "txt-slides": "slides.pptx", "csv": "sample.csv"}[source]
            run("soffice", profile, "--headless", "--convert-to", flt, "--outdir", str(work / "out"), src, cwd=work)
            produced = work / "out" / (Path(src).stem + "." + target)
            shutil.copyfile(produced, OUT / ("sample." + target))
        shutil.copyfile(work / "sample.odt", OUT / "sample.odt")
        # Plain-text family: written directly, they are text by definition.
        (OUT / "sample.txt").write_text("\n".join(TEXT) + "\n✨ emoji line\n", encoding="utf-8")
        (OUT / "sample.md").write_text("# " + TEXT[0] + "\n\n" + TEXT[1] + "\n", encoding="utf-8")
        (OUT / "sample.csv").write_text("Name,Note\nfixture,café\nsecond,naïve\n", encoding="utf-8")
        (OUT / "sample.json").write_text(json.dumps({"title": TEXT[0], "note": TEXT[1]}, ensure_ascii=False) + "\n", encoding="utf-8")
        (OUT / "sample.html").write_text("<!doctype html><title>fixture</title><p>" + TEXT[0] + "</p>\n", encoding="utf-8")
        (OUT / "sample.fountain").write_text("INT. STUDIO - NIGHT\n\nJOSIE\n" + TEXT[1] + "\n", encoding="utf-8")
        (OUT / "sample.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><rect width="40" height="20" fill="#c84"/></svg>\n', encoding="utf-8")
        # Images: a small picture with an asymmetric mark, so a rotation is detectable.
        picture = Image.new("RGB", (40, 20), (200, 140, 70))
        ImageDraw.Draw(picture).rectangle([0, 0, 9, 9], fill=(20, 20, 160))
        for ext, fmt in (("png", "PNG"), ("jpg", "JPEG"), ("gif", "GIF"), ("webp", "WEBP"), ("bmp", "BMP")):
            picture.save(OUT / ("sample." + ext), fmt)
        # Media: one second, small.
        tone = ["-f", "lavfi", "-i", "sine=frequency=440:duration=1"]
        video = ["-f", "lavfi", "-i", "testsrc=size=64x48:rate=10:duration=1"]
        audio_targets = {"wav": [], "mp3": ["-b:a", "32k"], "ogg": ["-c:a", "libvorbis"], "opus": ["-c:a", "libopus", "-b:a", "24k"],
                         "flac": [], "m4a": ["-c:a", "aac", "-b:a", "32k"]}
        for ext, extra in audio_targets.items():
            run("ffmpeg", "-y", "-loglevel", "error", *tone, *extra, str(OUT / ("sample." + ext)))
        video_targets = {"mp4": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "32k"],
                         "webm": ["-c:v", "libvpx-vp9", "-b:v", "50k", "-c:a", "libopus", "-b:a", "24k"],
                         "mov": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "32k"]}
        for ext, extra in video_targets.items():
            run("ffmpeg", "-y", "-loglevel", "error", *video, *tone, "-shortest", *extra, str(OUT / ("sample." + ext)))
        # An unknown binary that must be preserved byte for byte.
        (OUT / "sample.bin").write_bytes(bytes(range(256)) * 4)
    manifest = {p.name: {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in sorted(OUT.iterdir()) if p.name.startswith("sample.")}
    tools = {}
    for tool, flag in (("soffice", "--version"), ("pandoc", "--version"), ("ffmpeg", "-version")):
        tools[tool] = subprocess.run([tool, flag], capture_output=True, text=True).stdout.splitlines()[0]
    (OUT / "MANIFEST.json").write_text(json.dumps({"text": TEXT, "producers": tools, "files": manifest}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(manifest)} fixtures, {sum(v['bytes'] for v in manifest.values())} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
