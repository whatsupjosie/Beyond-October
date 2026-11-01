"""Alex's persistent memory must reach Alex's own private prompt, and only there."""
import pytest

from modules.alex_core import AlexCore, _tokens
from modules.alex_jeremy_bridge import AlexJeremyBridge
from modules.jeremy_cricket import CricketKeeper
from modules.pubpartner_core import PubPartnerSpine

LIMITED = {"classification": "LIMITED", "categories": ["HEALTH"], "subject_id": "u", "origin_event_id": "m"}


def test_keywords_are_clean_words_not_punctuated_filler(tmp_path):
    core = AlexCore(user_id="u", data_dir=tmp_path)
    kws = core.memory._extract_keywords("Sorry. Let's try again, my sister's visiting Friday!! Good, thanks.")
    assert "friday" in kws and "visiting" in kws
    assert not any(k in kws for k in ("sorry.", "let's", "again,", "good,", "thanks.", "thanks", "good"))
    assert all(k == k.strip(".,!?;:") for k in kws)
    assert _tokens("Visiting? Friday!") == ["visiting", "friday"]


@pytest.mark.asyncio
async def test_recall_matches_punctuated_queries_and_old_punctuated_disk_keywords(tmp_path):
    core = AlexCore(user_id="u", data_dir=tmp_path)
    await core.process_message("my sister is visiting on friday", metadata={"session_id": "s", "message_id": "m1"})
    assert [m.content for m in core.memory.recall(query="Is my sister visiting?")]
    # a memory written by the old extractor (punctuated keywords) is still found after reload
    node = next(m for ms in core.memory._diary.values() for m in ms)
    node.keywords = ["visiting,", "friday."]
    core.memory._save_memory(node)
    reloaded = AlexCore(user_id="u", data_dir=tmp_path)
    assert reloaded.memory.recall(query="friday visiting?")


@pytest.mark.asyncio
async def test_speaker_recall_is_relevant_bounded_and_empty_without_a_match(tmp_path):
    bridge = AlexJeremyBridge(data_dir=tmp_path)
    for i, t in enumerate(["my sister is visiting friday so I need to be done by thursday",
                           "the rust build finally compiled", "ok that is enough for today"]):
        await bridge.process_user_turn(user_id="u", session_id="s", text=t, metadata={"message_id": f"m{i}"})
    hit = bridge.recalled_for_speaker(user_id="u", query="what was happening with my sister?")
    assert hit and "sister" in hit[0]["text"] and len(hit) <= 3
    assert bridge.recalled_for_speaker(user_id="u", query="completely unrelated gardening question") == []
    assert bridge.recalled_for_speaker(user_id="nobody", query="sister") == []
    assert bridge.recalled_for_speaker(user_id="u", query="  ") == []
    long = await bridge.process_user_turn(user_id="u", session_id="s", text="budget " + "word " * 200,
                                          metadata={"message_id": "mlong"})
    assert all(len(r["text"]) <= 280 for r in bridge.recalled_for_speaker(user_id="u", query="budget"))
    # the shared packet never carries remembered content
    assert "need to be done by thursday" not in str(bridge.current_packet(user_id="u", session_id="s")).lower()
    bridge.shutdown()


@pytest.mark.asyncio
async def test_limited_turn_is_not_stored_or_recalled_unless_policy_allows(tmp_path):
    bridge = AlexJeremyBridge(data_dir=tmp_path)
    await bridge.process_user_turn(user_id="u", session_id="s", text="my private diagnosis zebra",
                                   metadata={"message_id": "m1", "data_handling": LIMITED})
    assert bridge.recalled_for_speaker(user_id="u", query="diagnosis zebra") == []
    allowed = {**LIMITED, "handling": {"allow_persistent_memory": True}}
    await bridge.process_user_turn(user_id="u", session_id="s", text="my allowed memory giraffe",
                                   metadata={"message_id": "m2", "data_handling": allowed})
    assert bridge.recalled_for_speaker(user_id="u", query="allowed giraffe")
    with pytest.raises(ValueError):                       # the bridge refuses an unknown classification
        await bridge.process_user_turn(user_id="u", session_id="s", text="bad label okapi",
                                       metadata={"message_id": "m3", "data_handling": {"classification": "NONSENSE"}})
    # AlexCore used directly fails closed too: nothing is stored under an unreadable label
    core = AlexCore(user_id="direct", data_dir=tmp_path / "direct")
    await core.process_message("bad label okapi", metadata={"session_id": "s", "data_handling": {"classification": "NONSENSE"}})
    assert core.memory.recall(query="label okapi") == [] or all("okapi" not in m.content for m in core.memory.recall(query="label okapi"))
    bridge.shutdown()


@pytest.mark.asyncio
async def test_spine_gives_alex_memory_to_private_turns_only(tmp_path):
    bridge = AlexJeremyBridge(tmp_path)
    keeper = CricketKeeper(tmp_path / "jeremy")
    await keeper.init()
    spine = PubPartnerSpine(tmp_path, alex_bridge=bridge, cricket_keeper=keeper)
    friend = {"friend_id": "alex", "display_name": "Alex"}
    for room in ("phone", "lobby"):
        await spine.create_session(user_id="u", session_id=f"s-{room}", project_id="p", room_id=room)
        await spine.build_turn_packet(user_id="u", session_id=f"s-{room}", message="the zebra crossing report is due thursday",
                                      project_id="p", room_id=room, friend=friend, provider={"provider": "gpt", "model": "t"})
        turn = await spine.build_turn_packet(user_id="u", session_id=f"s-{room}", message="what about the zebra report?",
                                             project_id="p", room_id=room, friend=friend,
                                             provider={"provider": "gpt", "model": "t"})
        srcs = {m["src"] for m in turn["fcp1"]["m"]}
        if room == "phone":
            assert "alex_memory" in srcs, "private turn must carry Alex's remembered content"
        else:
            assert "alex_memory" not in srcs, "shared rooms must never receive Alex's private memory"
    bridge.shutdown()
