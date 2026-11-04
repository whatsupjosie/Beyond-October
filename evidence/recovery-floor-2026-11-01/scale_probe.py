"""Disposable, reproducible 64 MiB/500-file checkpoint exercise; no host launch."""
from __future__ import annotations

import hashlib
import json
import platform
import random
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from modules.data_checkpoint import create_checkpoint, restore_checkpoint


def sha(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main() -> None:
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as folder:
        base = Path(folder)
        source = base / "data"
        source.mkdir()
        block = random.Random(26).randbytes(1024 * 1024)
        media = source / "recorded-bytes.bin"
        with media.open("wb") as stream:
            for _ in range(64):
                stream.write(block)
        records = source / "records"
        records.mkdir()
        for index in range(500):
            (records / f"record-{index:04d}.json").write_text(json.dumps({"ordinal": index, "exact_text": "Retain these words.\n"}), encoding="utf-8")
        original = sha(media)
        captured = create_checkpoint(source, base / "checkpoint.zip", offline=True,
                                     source_revision="disposable-scale-probe")
        source.rename(base / "original-unavailable")
        restored = restore_checkpoint(base / "checkpoint.zip", base / "recovered",
                                      expected_sha256=captured["sha256"])
        data = Path(restored["data_dir"])
        assert sha(data / "recorded-bytes.bin") == original
        assert len(list((data / "records").glob("*.json"))) == 500
        result = {"ok": True, "ran_at": datetime.now(timezone.utc).isoformat(),
                  "python": platform.python_version(), "platform": platform.system(),
                  "files": captured["file_count"], "uncompressed_bytes": captured["bytes"],
                  "media_bytes": 64 * 1024 * 1024, "media_sha256": original,
                  "checkpoint_sha256": captured["sha256"],
                  "exact_original_bytes_restored": True,
                  "original_path_unavailable_during_restore": True,
                  "elapsed_seconds": round(time.monotonic() - started, 3),
                  "scope": "Disposable files, not a production media codec or full application acceptance test"}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
