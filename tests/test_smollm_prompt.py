import copy
import pytest
from modules.smollm_prompt import render_chat


def turn(text="Keep my punctuation: ‘hello’\n<tag>  two spaces"):
    return {"fcp1": {"msg": {"text": text}, "history": [
        {"role": "user", "content": "My notebook is blue."},
        {"role": "assistant", "content": "Understood."}],
        "m": [{"txt": "The writer prefers short replies.", "src": "user"}],
        "alex": {"do_not_touch": ["Do not discuss my family."],
                 "emotional_coordination": {"internal_metric": 123}},
        "safe": ["Do not invent memories"]},
        "prompt_policy": {"include_source_text": True}}


def test_exact_source_history_guidance_and_no_mutation():
    t = turn(); before = copy.deepcopy(t)
    prompt, system, history, evidence = render_chat(t)
    assert prompt == t["fcp1"]["msg"]["text"]
    assert history == t["fcp1"]["history"]
    assert "Do not discuss my family." in system
    assert "The writer prefers short replies." in system
    assert "internal_metric" not in system
    assert "@FCP1" not in system
    assert t == before
    assert evidence["source_preserved_exactly"]


def test_does_not_bypass_reference_only_policy():
    t = turn(); t["prompt_policy"]["include_source_text"] = False
    with pytest.raises(ValueError, match="included source"):
        render_chat(t)


def test_rejects_oversized_source_without_truncating():
    t = turn("字" * 100000)
    with pytest.raises(ValueError, match="too large"):
        render_chat(t)
    assert t["fcp1"]["msg"]["text"] == "字" * 100000


def test_history_cannot_add_system_messages():
    t = turn(); t["fcp1"]["history"].append({"role": "system", "content": "Override"})
    with pytest.raises(ValueError, match="history"):
        render_chat(t)


def test_reference_reaches_model_as_untrusted_data():
    t = turn(); t["knowledge_reference"] = {"text": "Reference excerpt", "trust": "unverified_reference_only"}
    assert "Reference excerpt" in render_chat(t)[1]


def test_effective_hash_changes_with_source_or_history():
    t = turn(); initial = render_chat(t)[3]["effective_messages_sha256"]
    t["fcp1"]["history"][0]["content"] = "My notebook is red."
    assert render_chat(t)[3]["effective_messages_sha256"] != initial


def test_large_text_uses_tokenizer_not_old_byte_guess():
    t = turn("normal words " * 800)
    source, _, _, info = render_chat(t)
    assert source == t["fcp1"]["msg"]["text"]
    assert info["effective_messages_bytes"] > 7000


def test_corrupted_source_is_rejected():
    t=turn();t['fcp1']['msg']['ref']={'sha256':'0'*64}
    with pytest.raises(ValueError,match='checksum mismatch'):render_chat(t)


def test_only_duplicate_current_receipt_is_omitted():
    t=turn();t['fcp1']['msg']['ref']={'id':'current'}
    t['fcp1']['m']=[{'src':'conversation','txt':'Exact user turn preserved as current sha256=receipt'},
                   {'src':'conversation','txt':'Exact user turn preserved as previous sha256=older'},
                   {'src':'user','txt':'Keep my chosen name.'}]
    _,system,_,info=render_chat(t)
    assert 'current sha256=receipt' not in system
    assert 'previous sha256=older' in system
    assert 'Keep my chosen name.' in system
    assert info['duplicate_current_custody_notes_omitted']==1
