from modules.voxel_block_kit import backdrop_panel, doorway_wall, guide_grid, make_voxel_set, stage_floor
from modules.voxel_set_contract import inches_to_pub_units, normalize_voxel_set, pub_block_measurement, pub_units_to_inches, theater_platform_set


def test_pubblock_measurement_defaults_to_ten_inches():
    measurement = pub_block_measurement()
    assert measurement["base_block_inches"] == 10
    assert measurement["unit_inches"] == 10
    assert measurement["unit_profile"] == "pub_block_10in"


def test_pubblock_half_and_quarter_units_are_exact():
    assert pub_block_measurement(2)["unit_inches"] == 5
    assert pub_block_measurement(4)["unit_inches"] == 2.5
    assert inches_to_pub_units(72, subdivision=1) == 7
    assert inches_to_pub_units(72, subdivision=4) == 29
    assert pub_units_to_inches(4, subdivision=4) == 10


def test_voxel_set_normalizes_measurement_metadata():
    voxel_set = theater_platform_set("pubblock_measurement_test")
    assert voxel_set["measurement"]["base_block_inches"] == 10
    assert voxel_set["unit_profile"] == "pub_block_10in"


def test_voxel_block_kit_builds_stage_floor_with_guides_hidden_from_program():
    blocks = stage_floor(width=4, depth=3) + guide_grid(width=4, depth=3)
    voxel_set = make_voxel_set("floor_with_guides", "Floor With Guides", blocks)
    guide_blocks = [block for block in voxel_set["blocks"] if block["material"] == "guide"]
    assert guide_blocks
    assert all(block["metadata"].get("visible_to_program") is False for block in guide_blocks)


def test_voxel_block_kit_supports_backdrops_and_doorways():
    blocks = backdrop_panel(width=6, height=4, z=5, image_id="city_lot") + doorway_wall(width=6, height=10, door_x=2, door_width=2)
    voxel_set = make_voxel_set("backdrop_and_doorway", "Backdrop And Doorway", blocks)
    assert normalize_voxel_set(voxel_set)["asset_id"] == "backdrop_and_doorway"
    assert any(block["material"] == "backdrop" for block in voxel_set["blocks"])
