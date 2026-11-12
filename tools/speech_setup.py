"""Explicit, pinned speech asset installation. Never invoked by the server."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

SPEC = json.loads(Path(__file__).with_name("speech_assets.json").read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def verify(target: Path, name: str) -> dict:
    manifest = json.loads((target / "INSTALL.json").read_text(encoding="utf-8"))
    if manifest["revision"] != SPEC[name]["revision"] or manifest["repository"] != SPEC[name]["repository"]:
        raise ValueError("Existing installation has different provenance: " + str(target))
    required = {"model.onnx", "voices.bin"} if name == "kokoro" else {"model.bin", "config.json", "tokenizer.json", "vocabulary.txt"}
    if not required.issubset(manifest["assets"]):
        raise ValueError("Incomplete asset inventory: " + str(target))
    for relative, expected in manifest["assets"].items():
        path = target / "assets" / relative
        if not path.resolve().is_relative_to((target / "assets").resolve()) or path.is_symlink() or digest(path) != expected:
            raise ValueError("Local speech asset failed verification: " + str(path))
    return {"model": name, "verified": True, "revision": manifest["revision"], "files": len(manifest["assets"])}


def install(data: Path, name: str, source_dir: Path | None = None) -> dict:
    models = data / "speech" / "models"
    models.mkdir(parents=True, exist_ok=True)
    target = models / name
    if target.exists():
        return verify(target, name)  # Never replace an existing installation.
    spec = SPEC[name]
    with tempfile.TemporaryDirectory(prefix=".speech-install-", dir=models) as temporary:
        staging = Path(temporary)
        assets = staging / "assets"
        assets.mkdir()
        source = staging / "source"
        source.mkdir()
        for relative, expected in spec["files"].items():
            if source_dir is None:
                from huggingface_hub import hf_hub_download
                original = Path(hf_hub_download(spec["repository"], relative, revision=spec["revision"]))
            else:
                original = source_dir / relative
            if digest(original) != expected:
                raise ValueError("Source checksum mismatch: " + relative)
            local = source / relative
            local.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, local)
        if name == "kokoro":
            import numpy as np
            shutil.copyfile(source / "onnx/model_quantized.onnx", assets / "model.onnx")
            styles = {}
            for voice in sorted((source / "voices").glob("*.bin")):
                values = np.fromfile(voice, dtype="<f4")
                if len(values) != 510 * 256 or not np.isfinite(values).all():
                    raise ValueError("Invalid English voice style: " + voice.name)
                styles[voice.stem] = values.reshape(-1, 1, 256)
            with (assets / "voices.bin").open("wb") as output:
                np.savez(output, **styles)  # Lossless repack for kokoro-onnx.
            shutil.copyfile(source / "README.md", assets / "MODEL_README.md")
        else:
            for relative in spec["files"]:
                shutil.copyfile(source / relative, assets / relative)
        manifest = {"repository": spec["repository"], "revision": spec["revision"],
                    "source_sha256": spec["files"], "assets": {p.name: digest(p) for p in sorted(assets.iterdir())}}
        (staging / "INSTALL.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        # Exclusive container claim; concurrent installers cannot clobber files.
        target.mkdir()
        os.rename(assets, target / "assets")
        os.rename(staging / "INSTALL.json", target / "INSTALL.json")
    return verify(target, name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--model", choices=[*SPEC, "all"], default="all")
    parser.add_argument("--verify", action="store_true", help="Verify local files without network access")
    parser.add_argument("--source-dir", type=Path, help="Use already downloaded, checksum-verified source files (one model only)")
    options = parser.parse_args()
    names = list(SPEC) if options.model == "all" else [options.model]
    if options.source_dir and len(names) != 1:
        parser.error("--source-dir requires one --model")
    try:
        results = [verify(options.data_dir / "speech/models" / name, name) if options.verify else
                   install(options.data_dir, name, options.source_dir) for name in names]
        print(json.dumps({"ok": True, "models": results}, indent=2))
        return 0
    except (OSError, ValueError, KeyError, ImportError) as error:
        parser.exit(1, "Speech installation failed: " + str(error) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
