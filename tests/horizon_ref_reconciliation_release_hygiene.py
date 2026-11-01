from __future__ import annotations

from pathlib import Path

from scripts.sanitize_release import sanitize


def test_sanitizer_removes_runtime_secrets_user_profiles_and_generated_state(tmp_path: Path):
    fixtures = {
        "data/byok/secure/master.key": "secret",
        "data/secure/master.key": "secret",
        "data/users.db": "db",
        "data/global/dm_requests.sqlite3": "db",
        "data/conversation_archive/conversations.sqlite3": "db",
        "data/memory/pubcast_memory.db": "db",
        "data/memory_snapshot.json": "{}",
        "data/writers_room/documents.sqlite3": "db",
        "data/alex/josie/_alex_state.json": "{}",
        "data/blackbox/capture.bbx": "runtime",
        "data/dressing_room_security/josie.json": "{}",
        "data/pub_partner_chat/default_default.jsonl": "{}\n",
        "data/sessions/private-session.json": "{}",
        "data/pubpartner/profiles/users/josie.json": "{}",
        "data/emergency_bridge/commands/cmd.json": "{}",
        "data/logs/production.jsonl": "{}\n",
        "data/recordings/test_session/session.json": "{}",
    }
    for rel, text in fixtures.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    sanitize(tmp_path)

    for rel in fixtures:
        assert not (tmp_path / rel).exists()
    assert (tmp_path / "data/pubpartner/profiles/users/.gitkeep").is_file()
    assert (tmp_path / "data/byok/secure/.gitkeep").is_file()
    assert (tmp_path / "data/secure/.gitkeep").is_file()
    for rel in (
        "data/alex",
        "data/blackbox",
        "data/conversation_archive",
        "data/dressing_room_security",
        "data/pub_partner_chat",
        "data/sessions",
        "data/memory",
        "data/writers_room",
        "data/global",
    ):
        assert (tmp_path / rel / ".gitkeep").is_file()
