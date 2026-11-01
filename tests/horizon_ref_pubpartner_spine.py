import json

import pytest

from modules.alex_jeremy_bridge import AlexJeremyBridge
from modules.jeremy_cricket import CricketKeeper
from modules.pubpartner_core import PubPartnerSpine, VerbatimVault


@pytest.mark.asyncio
async def test_verbatim_vault_preserves_exact_multilingual_text(tmp_path):
    vault = VerbatimVault(tmp_path)
    original = "Verse 1\nFeic mo chroí — 唔好改呢句。\n  keep  spaces  \n"
    rec = vault.store(user_id="josie", session_id="s1", text=original, kind="lyrics", language="en+yue")

    restored = vault.load(user_id="josie", session_id="s1", source_id=rec.source_id)

    assert restored.text == original
    assert restored.sha256 == rec.sha256
    assert restored.kind == "lyrics"
    assert restored.byte_len == len(original.encode("utf-8"))


@pytest.mark.asyncio
async def test_pubpartner_spine_builds_fcp1_without_losing_source_text(tmp_path):
    alex_bridge = AlexJeremyBridge(tmp_path)
    keeper = CricketKeeper(tmp_path / "jeremy")
    await keeper.init()
    spine = PubPartnerSpine(tmp_path, alex_bridge=alex_bridge, cricket_keeper=keeper)

    await spine.create_session(user_id="josie", session_id="s1", project_id="pubpartner", room_id="phone")
    exact = "Chorus:\nI keep my heart where the gold light lands\nDo not rewrite this line."
    turn = await spine.build_turn_packet(
        user_id="josie",
        session_id="s1",
        message=exact,
        project_id="pubpartner",
        room_id="phone",
        content_kind="lyrics",
        friend={"friend_id": "craig", "display_name": "Craig", "tone": ["warm", "dry"]},
        provider={"provider": "gpt", "model": "test"},
        task={"mode": "songwriting", "goal": "comment_without_rewriting"},
    )

    assert turn["ok"] is True
    assert turn["verbatim_restores"] is True
    assert turn["fcp1"]["v"] == "FCP1"
    assert turn["fcp1"]["msg"]["text"] == exact
    assert turn["fcp1"]["msg"]["ref"]["sha256"] == turn["source"]["sha256"]
    assert "do_not_alter_exact_text" in turn["fcp1"]["task"]["guard"]
    assert "msg<<FCP1_VERBATIM" in turn["fcp1_text"]

    restored = spine.restore_source(user_id="josie", session_id="s1", source_id=turn["source"]["id"])
    assert restored["text"] == exact

    cricket = await keeper.get("craig")
    memories = await cricket.recall("gold light lands", max_results=5)
    assert any(turn["source"]["id"] in m.content for m in memories)
    await keeper.close_all()
    alex_bridge.shutdown()


def test_fcp1_json_is_parseable_and_keeps_msg_ref(tmp_path):
    vault = VerbatimVault(tmp_path)
    rec = vault.store(user_id="u", session_id="s", text="hello", kind="message")
    from modules.pubpartner_core import FCP1Packet, FriendProfile, ProviderProfile, UserPrimer

    packet = FCP1Packet(
        language="en-US",
        user=UserPrimer(user_id="u"),
        friend=FriendProfile(friend_id="craig", display_name="Craig"),
        provider=ProviderProfile(provider="local", model="tiny"),
        task={"mode": "chat"},
        project={"id": "p"},
        safety=["privacy_first"],
        output={"fmt": "plain"},
        source=rec,
    )
    data = json.loads(packet.as_json())
    assert data["msg"]["ref"]["id"] == rec.source_id
    assert data["msg"]["text"] == "hello"


def test_verbatim_vault_detects_sidecar_tampering(tmp_path):
    vault = VerbatimVault(tmp_path)
    original = "Exact lyric line\nwith spacing  preserved\n"
    rec = vault.store(user_id="josie", session_id="tamper", text=original, kind="lyrics")
    raw_path = vault._raw_path("josie", "tamper", rec.source_id)
    raw_path.write_bytes(b"Exact lyric line\nwith spacing changed\n")

    with pytest.raises(ValueError, match="raw-byte hash mismatch"):
        vault.load(user_id="josie", session_id="tamper", source_id=rec.source_id)


@pytest.mark.asyncio
async def test_token_light_prompt_can_omit_long_exact_source_while_full_packet_preserves_it(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    long_lyrics = "Chorus:\n" + "Never rewrite this exact line.\n" * 140
    turn = await spine.build_turn_packet(
        user_id="josie",
        session_id="longexact",
        message=long_lyrics,
        content_kind="lyrics",
        prompt_mode="auto",
        task={"mode": "songwriting", "goal": "analyze_without_rewriting"},
    )

    assert turn["prompt_policy"]["mode"] == "auto_ref_only"
    assert "Never rewrite this exact line" in turn["fcp1_text"]
    assert "Never rewrite this exact line" not in turn["llm_prompt_text"]
    assert "requires_restore_before_quote" in json.dumps(turn["prompt_policy"])

    restored = spine.restore_source(user_id="josie", session_id="longexact", source_id=turn["source"]["id"])
    assert restored["text"] == long_lyrics
    assert restored["source"]["sha256"] == turn["source"]["sha256"]


def test_fcp1_ref_only_packet_marks_source_policy_and_omits_text(tmp_path):
    vault = VerbatimVault(tmp_path)
    rec = vault.store(user_id="u", session_id="s", text="line one\nline two", kind="quote")
    from modules.pubpartner_core import FCP1Packet, FriendProfile, ProviderProfile, UserPrimer

    packet = FCP1Packet(
        language="en-US",
        user=UserPrimer(user_id="u"),
        friend=FriendProfile(friend_id="craig", display_name="Craig"),
        provider=ProviderProfile(provider="local", model="tiny"),
        task={"mode": "quote_check"},
        project={"id": "p"},
        safety=["privacy_first"],
        output={"fmt": "plain"},
        source=rec,
    )
    data = json.loads(packet.as_json(include_source_text=False))
    assert data["source_policy"]["immutable"] is True
    assert data["source_policy"]["quote_policy"] == "quote_only_after_restoring_msg_ref"
    assert data["msg"]["text_status"] == "omitted_ref_only"
    assert "text" not in data["msg"]
    assert data["msg"]["preview"] == "line one\\nline two"


def test_verbatim_vault_rejects_missing_sealed_sidecar(tmp_path):
    vault = VerbatimVault(tmp_path)
    rec = vault.store(user_id="josie", session_id="missing_sidecar", text="exact", kind="quote")
    vault._raw_path("josie", "missing_sidecar", rec.source_id).unlink()

    with pytest.raises(ValueError, match="sidecar missing"):
        vault.load(user_id="josie", session_id="missing_sidecar", source_id=rec.source_id)


def test_verbatim_vault_verifies_hash_chained_audit(tmp_path):
    vault = VerbatimVault(tmp_path)
    rec1 = vault.store(user_id="josie", session_id="audit", text="one", kind="message")
    rec2 = vault.store(user_id="josie", session_id="audit", text="two", kind="message")

    status = vault.verify_session_audit(user_id="josie", session_id="audit")
    assert status["ok"] is True
    assert status["entries"] == 2
    assert status["source_ids"] == [rec1.source_id, rec2.source_id]

    audit = vault._audit_path("josie", "audit")
    lines = audit.read_text(encoding="utf-8").splitlines()
    payload = json.loads(lines[1])
    payload["prev_audit_hash"] = "broken"
    lines[1] = json.dumps(payload)
    audit.write_text("\n".join(lines) + "\n", encoding="utf-8")

    broken = vault.verify_session_audit(user_id="josie", session_id="audit")
    assert broken["ok"] is False
    assert "audit hash mismatch" in broken["error"] or "audit chain break" in broken["error"]


@pytest.mark.asyncio
async def test_restore_source_span_is_exact_and_turn_log_does_not_duplicate_full_text(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    exact = "alpha\nβeta line\ngamma\n"
    turn = await spine.build_turn_packet(
        user_id="josie",
        session_id="spanlog",
        message=exact,
        content_kind="poetry",
        prompt_mode="full",
    )
    start = exact.index("β")
    end = exact.index("gamma")
    span = spine.restore_source_span(
        user_id="josie",
        session_id="spanlog",
        source_id=turn["source"]["id"],
        start=start,
        end=end,
    )
    assert span["span"]["text"] == exact[start:end]
    assert span["span"]["sha256"]

    log_path = tmp_path / "pubpartner" / "sessions" / "josie_spanlog_turns.jsonl"
    logged = json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert logged["fcp1"]["msg"]["text_status"] == "omitted_turn_log_ref_only"
    assert "text" not in logged["fcp1"]["msg"]
    assert exact not in log_path.read_text(encoding="utf-8")


def test_compact_text_contains_source_policy_when_ref_only(tmp_path):
    vault = VerbatimVault(tmp_path)
    rec = vault.store(user_id="u", session_id="s", text="x" * 2000, kind="lyrics")
    from modules.pubpartner_core import FCP1Packet, FriendProfile, ProviderProfile, UserPrimer

    packet = FCP1Packet(
        language="en-US",
        user=UserPrimer(user_id="u"),
        friend=FriendProfile(friend_id="craig", display_name="Craig"),
        provider=ProviderProfile(provider="local", model="tiny"),
        task={"mode": "song"},
        project={"id": "p"},
        safety=["privacy_first"],
        output={"fmt": "plain"},
        source=rec,
    )
    text = packet.as_compact_text(include_source_text=False)
    assert "source_policy=" in text
    assert "quote_only_after_restoring_msg_ref" in text
    assert "x" * 100 not in text
