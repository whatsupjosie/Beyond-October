from unittest.mock import patch
import pytest
from pubpartner.pubpartner_federation.docking import DockingNode


def test_caught_inner_write_failure_does_not_commit_its_partial_data(tmp_path):
    node = DockingNode(tmp_path, owner_id="owner", role="resident")
    try:
        with node.store.transaction():
            with patch.object(node.store, "record_change", side_effect=OSError("interrupted")):
                with pytest.raises(OSError):
                    node.record_knowledge("bad", text="Must not persist", friend_id="alex",
                        source_ref="owner", confirmed=True)
            node.record_knowledge("good", text="Must persist", friend_id="alex",
                source_ref="owner", confirmed=True)
        entities = node.store.all_entities()
        assert [entity.fields["text"] for entity in entities] == ["Must persist"]
        assert node.engine.clock == node.store.load_clock()
    finally:
        node.close()
