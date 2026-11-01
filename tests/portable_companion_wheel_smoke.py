"""Run with python -I SCRIPT WHEEL to verify Horizon without a PubCast tree."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import sys
from importlib.metadata import version

wheel = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(wheel))

from pubpartner.cartridge import init_cartridge, load_cartridge
from pubpartner.portable_runtime import PortableRuntime
from pubpartner.pubpartner_federation.docking import DockingNode
from pubpartner.sequence_controller import SequenceController
from pubpartner import __version__

assert version("pubpartner") == __version__, "Wheel metadata and public API version disagree"

with TemporaryDirectory() as directory:
    root = Path(directory)
    init_cartridge(root / "alex", name="Alex", summary="Curious and attentive.",
                   cadence="short", vocabulary="plain")
    cartridge = load_cartridge(root / "alex")
    h = DockingNode(root / "h", owner_id="u", role="portable")
    b = DockingNode(root / "b", owner_id="u", role="resident")
    def create(**kwargs):
        assert "companion_advisory=" in kwargs["system"]
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="We can compare choices.")])
    runtime = PortableRuntime(cartridge, llm_client=SimpleNamespace(messages=SimpleNamespace(create=create)),
        subject_id="u", friend_id="alex", docking_node=h,
        sequencer=SequenceController(debounce_seconds=0))
    try:
        runtime.submit_input("I am excited about the Lantern design. Can you help me plan?")
        result = runtime.run_turn()
        b.record_knowledge("fact", text="Lantern design uses tidal power", friend_id="alex",
                           source_ref="owner", confirmed=True)
        assert h.dock(b)["status"] == "synced"
        assert {x.entity_type for x in b.store.all_entities()} == {"memory", "knowledge", "experience"}
        assert result.companion_review["response_modified"] is False
        assert h.recall(owner_id="u", friend_id="alex", query="tidal")["items"]
        assert not any(name == "modules" or name.startswith("modules.") for name in sys.modules)
        assert ".whl/" in sys.modules["pubpartner.portable_runtime"].__file__
        print(json.dumps({"wheel": wheel.name, "status": "passed", "pubcast_imports": 0,
                          "advisory": True, "bidirectional_docking": True}))
    finally:
        runtime.close()
        h.close()
        b.close()
