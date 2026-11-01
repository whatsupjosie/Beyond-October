import json
from pathlib import Path


def test_principal_avatar_manifest_marks_manny_and_sheila_as_3d_performers():
    manifest = json.loads(Path("data/avatars/manifest.json").read_text(encoding="utf-8"))
    assets = {
        asset["id"]: asset
        for pack in manifest["packs"]
        for asset in pack["assets"]
    }
    for avatar_id in ("manny", "sheila"):
        asset = assets[avatar_id]
        assert asset["asset_type"] == "glb"
        assert asset["performer_asset"] is True
        assert asset["production_avatar"] is True
        assert asset["sprite_replacement_allowed"] is False
        assert Path(asset["path"]).exists()
        assert "visible" in asset["fallback_policy"].lower()
