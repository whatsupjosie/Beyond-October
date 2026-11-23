"""Existing portable cartridge memory is reused by hosted PubPartner.

No new memory authority, no live LLM, no cross-owner exposure.
"""
import pytest

from modules.pubpartner_cartridges import CartridgeStudio
from modules.pubpartner_core import PubPartnerSpine
from pubpartner.cartridge import load_cartridge


@pytest.mark.asyncio
async def test_owned_portable_cartridge_memory_reaches_hosted_private_prompt(tmp_path):
    studio = CartridgeStudio(tmp_path)
    item = studio.create({"name": "Calypso", "summary": "A curious companion"}, owner="alice")
    with load_cartridge(studio.path_for(item["id"])) as cartridge:
        cartridge.memory.add("We built a brass-clock workshop together.", "episodic", importance=0.9)
    spine = PubPartnerSpine(tmp_path)
    result = await spine.build_turn_packet(
        user_id="alice", session_id="ours", room_id="phone",
        friend=item["id"], provider={"provider": "mock"},
        message="Do you remember our brass-clock workshop?"
    )
    assert result["cartridge_recall"] == {"status": "ok", "count": 1}
    assert any(row.get("src") == "cartridge_memory" and "brass-clock" in row.get("txt", "")
               for row in result["fcp1"]["m"])


@pytest.mark.asyncio
async def test_cartridge_memory_is_never_shared_with_other_user_or_public_room(tmp_path):
    studio = CartridgeStudio(tmp_path)
    item = studio.create({"name": "Calypso", "summary": "A curious companion"}, owner="alice")
    with load_cartridge(studio.path_for(item["id"])) as cartridge:
        cartridge.memory.add("PRIVATE_CARTRIDGE_MEMORY", "personal", importance=1.0)
    spine = PubPartnerSpine(tmp_path)
    for user, room in (("bob", "phone"), ("alice", "stage")):
        result = await spine.build_turn_packet(
            user_id=user, session_id="test", room_id=room,
            friend=item["id"], provider={"provider": "mock"},
            message="Tell me what you remember.",
        )
        assert result["cartridge_recall"]["status"] == "skipped"
        assert "PRIVATE_CARTRIDGE_MEMORY" not in result["llm_prompt_text"]


@pytest.mark.asyncio
async def test_builtin_friend_does_not_open_cartridge_storage(tmp_path):
    spine = PubPartnerSpine(tmp_path)
    result = await spine.build_turn_packet(
        user_id="alice", session_id="test", room_id="phone",
        friend="alex", provider={"provider": "mock"}, message="Hello",
    )
    assert result["cartridge_recall"]["reason"] == "not_a_cartridge"
