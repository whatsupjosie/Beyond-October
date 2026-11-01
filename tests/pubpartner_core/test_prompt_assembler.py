from pubpartner.cartridge import init_cartridge, load_cartridge
from pubpartner.prompt_assembler import assemble_prompt
from pubpartner.tokenizer import count_tokens


def _make_cartridge(tmp_path):
    cart_dir = tmp_path / "alex"
    init_cartridge(
        cart_dir,
        name="Alex",
        summary="A grounded, observant presence who notices what people don't say.",
        cadence="short sentences, pauses before the real point",
        vocabulary="plain, warm, precise",
    )
    return load_cartridge(cart_dir)


def test_character_block_always_present(tmp_path):
    cartridge = _make_cartridge(tmp_path)
    try:
        result = assemble_prompt(cartridge, query="", token_budget=2000)
        assert "Alex" in result.text
        assert "short sentences" in result.text
    finally:
        cartridge.close()


def test_relevant_memories_included(tmp_path):
    cartridge = _make_cartridge(tmp_path)
    try:
        cartridge.memory.add("Alex is currently learning to sail.", "project", importance=0.7)
        cartridge.memory.add("Alex dislikes cilantro.", "personal", importance=0.3)

        result = assemble_prompt(cartridge, query="tell me about sailing", token_budget=2000)
        assert result.memories_included >= 1
        assert "sail" in result.text
    finally:
        cartridge.close()


def test_respects_token_budget(tmp_path):
    cartridge = _make_cartridge(tmp_path)
    try:
        for i in range(200):
            cartridge.memory.add(f"Memory number {i} about a random Tuesday afternoon.", "episodic")

        result = assemble_prompt(cartridge, query="Tuesday afternoon", token_budget=300, max_memories=200)
        assert result.token_count <= 350  # small slack for the header itself
        assert result.truncated is True
    finally:
        cartridge.close()


def test_no_memories_still_produces_valid_prompt(tmp_path):
    cartridge = _make_cartridge(tmp_path)
    try:
        result = assemble_prompt(cartridge, query="hello", token_budget=2000)
        assert result.memories_included == 0
        assert result.token_count == count_tokens(result.text)
        assert "Alex" in result.text
    finally:
        cartridge.close()


def test_zero_budget_still_returns_character_block_gracefully(tmp_path):
    cartridge = _make_cartridge(tmp_path)
    try:
        cartridge.memory.add("Some memory.", "episodic")
        result = assemble_prompt(cartridge, query="memory", token_budget=1)
        # character block always included even if it blows the tiny budget
        assert "Alex" in result.text
        assert result.memories_included == 0
    finally:
        cartridge.close()
