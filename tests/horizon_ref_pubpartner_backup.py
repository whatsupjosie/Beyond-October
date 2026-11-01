from __future__ import annotations

from pathlib import Path
import zipfile

from modules.pubpartner_backup import create_friend_backup, verify_friend_backup


def test_friend_backup_is_verified_and_excludes_secrets(tmp_path: Path):
    root = tmp_path / "pubpartner"
    (root / "profiles" / "friends").mkdir(parents=True)
    (root / "profiles" / "friends" / "craig.json").write_text('{"name":"Craig"}', encoding="utf-8")
    (root / "relationship" / "josie" / "craig").mkdir(parents=True)
    (root / "relationship" / "josie" / "craig" / "lessons.json").write_text('{"lessons":[]}', encoding="utf-8")
    (root / "secure").mkdir(parents=True)
    (root / "secure" / "jwt_secret.txt").write_text("SECRET", encoding="utf-8")
    (root / "byok").mkdir(parents=True)
    (root / "byok" / "api_key.txt").write_text("KEY", encoding="utf-8")

    result = create_friend_backup(tmp_path, user_id="josie", friend_id="craig")
    assert result["ok"] is True
    assert result["contains_secrets"] is False
    assert verify_friend_backup(result["path"])["ok"] is True
    with zipfile.ZipFile(result["path"], "r") as zf:
        names = zf.namelist()
    assert not any("jwt_secret" in name or "api_key" in name or "/byok/" in name for name in names)
