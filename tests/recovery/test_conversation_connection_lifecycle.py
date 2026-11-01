"""SQLite context managers commit but don't close; verify actual handle cleanup."""
import sqlite3
import pytest
import modules.conversation_archive as archive_module


def test_archive_closes_real_connections_after_success_and_failure(tmp_path, monkeypatch):
    original_connect = sqlite3.connect
    handles = []

    class TrackedConnection(sqlite3.Connection):
        was_closed = False

        def close(self):
            self.was_closed = True
            return super().close()

    def tracked_connect(*args, **kwargs):
        connection = original_connect(*args, factory=TrackedConnection, **kwargs)
        handles.append(connection)
        return connection

    monkeypatch.setattr(archive_module.sqlite3, "connect", tracked_connect)
    archive = archive_module.ConversationArchive(tmp_path / "conversations.sqlite3")
    cid = archive.create_conversation(title="Close every connection")
    archive.append_message(cid, speaker="User", exact_text="verbatim")
    assert archive.get_conversation(cid)["messages"][0]["exact_text"] == "verbatim"
    assert archive.search('"verbatim"')
    with pytest.raises(sqlite3.OperationalError):
        archive.search('"unfinished')
    assert len(handles) >= 5
    assert all(connection.was_closed for connection in handles)
    with pytest.raises(sqlite3.ProgrammingError):
        handles[0].execute("SELECT 1")
