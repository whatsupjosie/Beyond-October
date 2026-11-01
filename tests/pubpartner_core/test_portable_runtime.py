import pytest

from pubpartner.cartridge import init_cartridge, load_cartridge
from pubpartner.portable_runtime import PortableRuntime, PortableRuntimeError
from pubpartner.sequence_controller import SequenceController


class FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeTextBlock(text)]


class FakeMessages:
    def __init__(self, reply_text="a fake reply"):
        self.reply_text = reply_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(self.reply_text)


class FakeAnthropicClient:
    def __init__(self, reply_text="a fake reply"):
        self.messages = FakeMessages(reply_text=reply_text)


class FakeClock:
    """Deterministic, manually-advanced clock — duplicated from
    test_sequence_controller.py deliberately so each test file stays
    independently runnable without cross-file imports."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def __call__(self) -> float:
        return self.now


def _make_cartridge_dir(tmp_path):
    cart_dir = tmp_path / "alex"
    init_cartridge(
        cart_dir,
        name="Alex",
        summary="Steady and observant.",
        cadence="short sentences",
        vocabulary="plain and warm",
    )
    return cart_dir


def _make_runtime(tmp_path, *, reply_text="a fake reply", sequencer=None, capture_memory=True):
    cart_dir = _make_cartridge_dir(tmp_path)
    cartridge = load_cartridge(cart_dir)
    client = FakeAnthropicClient(reply_text=reply_text)
    runtime = PortableRuntime(
        cartridge,
        sequencer=sequencer or SequenceController(debounce_seconds=0.0),
        llm_client=client,
        capture_episodic_memory=capture_memory,
    )
    return runtime, client


# ── Basic turn execution ─────────────────────────────────────────────────


def test_run_turn_returns_reply_and_metadata(tmp_path):
    runtime, client = _make_runtime(tmp_path, reply_text="hello there")
    try:
        runtime.submit_input("hi Alex")
        assert runtime.ready_for_turn() is True
        result = runtime.run_turn()
        assert result.user_text == "hi Alex"
        assert result.reply_text == "hello there"
        assert result.prompt_token_count > 0
        assert result.memory_id is not None
    finally:
        runtime.close()


def test_run_turn_sends_assembled_system_prompt(tmp_path):
    runtime, client = _make_runtime(tmp_path)
    try:
        runtime.submit_input("tell me about yourself")
        runtime.run_turn()
        sent = client.messages.calls[0]
        assert "Alex" in sent["system"]
        assert sent["messages"][0]["content"] == "tell me about yourself"
    finally:
        runtime.close()


def test_multiple_turns_accumulate_history(tmp_path):
    runtime, client = _make_runtime(tmp_path)
    try:
        runtime.submit_input("first message")
        runtime.run_turn()
        runtime.submit_input("second message")
        runtime.run_turn()
        second_call_messages = client.messages.calls[1]["messages"]
        assert len(second_call_messages) == 4  # user/assistant x2
        assert runtime.turn_count == 2
    finally:
        runtime.close()


def test_episodic_memory_captured_after_turn(tmp_path):
    runtime, client = _make_runtime(tmp_path)
    try:
        runtime.submit_input("I'm learning to sail")
        result = runtime.run_turn()
        memories = runtime._cartridge.memory.all(memory_type="episodic")
        assert len(memories) == 1
        assert memories[0].id == result.memory_id
        assert "learning to sail" in memories[0].text
    finally:
        runtime.close()


def test_memory_capture_can_be_disabled(tmp_path):
    runtime, client = _make_runtime(tmp_path, capture_memory=False)
    try:
        runtime.submit_input("this should not be remembered")
        result = runtime.run_turn()
        assert result.memory_id is None
        assert runtime._cartridge.memory.count() == 0
    finally:
        runtime.close()


# ── Debounce integration (sequencer actually gates run_turn) ─────────────


def test_ready_for_turn_false_before_debounce_elapses(tmp_path):
    clock = FakeClock()
    seq = SequenceController(debounce_seconds=1.0, clock=clock)
    runtime, client = _make_runtime(tmp_path, sequencer=seq)
    try:
        runtime.submit_input("hang on")
        assert runtime.ready_for_turn() is False
        clock.advance(1.1)
        assert runtime.ready_for_turn() is True
    finally:
        runtime.close()


def test_run_turn_without_ready_input_raises(tmp_path):
    runtime, client = _make_runtime(tmp_path)
    try:
        with pytest.raises(PortableRuntimeError):
            runtime.run_turn()
    finally:
        runtime.close()


# ── No-LLM-client path (prompt-only usage) ───────────────────────────────


def test_build_prompt_only_requires_no_client(tmp_path):
    cart_dir = _make_cartridge_dir(tmp_path)
    cartridge = load_cartridge(cart_dir)
    runtime = PortableRuntime(cartridge, llm_client=None)
    try:
        prompt = runtime.build_prompt_only(query="how are you")
        assert "Alex" in prompt
    finally:
        runtime.close()


def test_run_turn_without_client_raises_clear_error(tmp_path):
    cart_dir = _make_cartridge_dir(tmp_path)
    cartridge = load_cartridge(cart_dir)
    runtime = PortableRuntime(
        cartridge, sequencer=SequenceController(debounce_seconds=0.0), llm_client=None
    )
    try:
        runtime.submit_input("hello")
        assert runtime.ready_for_turn() is True
        with pytest.raises(PortableRuntimeError, match="requires an LLM client"):
            runtime.run_turn()
    finally:
        runtime.close()


# ── open() classmethod ────────────────────────────────────────────────────


def test_open_without_api_key_has_no_client(tmp_path):
    cart_dir = _make_cartridge_dir(tmp_path)
    runtime = PortableRuntime.open(cart_dir, api_key=None)
    try:
        assert runtime._llm_client is None
        # Prompt-only usage still works
        prompt = runtime.build_prompt_only()
        assert "Alex" in prompt
    finally:
        runtime.close()


def test_open_with_missing_cartridge_raises(tmp_path):
    from pubpartner.cartridge import CartridgeValidationError

    missing = tmp_path / "does_not_exist"
    with pytest.raises(FileNotFoundError):
        PortableRuntime.open(missing)


# ── Lifecycle ──────────────────────────────────────────────────────────────


def test_double_close_is_safe(tmp_path):
    runtime, client = _make_runtime(tmp_path)
    runtime.close()
    runtime.close()  # must not raise


def test_use_after_close_raises(tmp_path):
    runtime, client = _make_runtime(tmp_path)
    runtime.close()
    with pytest.raises(PortableRuntimeError):
        runtime.submit_input("too late")
    with pytest.raises(PortableRuntimeError):
        runtime.ready_for_turn()
    with pytest.raises(PortableRuntimeError):
        runtime.build_prompt_only()


def test_context_manager_closes_on_exit(tmp_path):
    cart_dir = _make_cartridge_dir(tmp_path)
    cartridge = load_cartridge(cart_dir)
    client = FakeAnthropicClient()
    with PortableRuntime(
        cartridge, sequencer=SequenceController(debounce_seconds=0.0), llm_client=client
    ) as runtime:
        runtime.submit_input("hi")
        runtime.run_turn()
    with pytest.raises(PortableRuntimeError):
        runtime.submit_input("after context exit")


def test_cartridge_name_accessible(tmp_path):
    runtime, client = _make_runtime(tmp_path)
    try:
        assert runtime.cartridge_name == "Alex"
    finally:
        runtime.close()
