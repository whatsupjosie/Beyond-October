"""Imported avatars: GLB measurement, canonical-height enforcement, storage and routes.

The browser converts any format to GLB; these tests prove the server side never
trusts it: heights are measured from the file itself, and a wrong-sized (Godzilla)
avatar is refused.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules import avatar_imports as AI

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "avatars"


# ── a tiny GLB builder so every geometry case is exact ──────────────────────

def make_glb(nodes, *, lo=(-0.2, 0.0, -0.1), hi=(0.2, 1.0, 0.1), skin=None, scenes=None, extra=None) -> bytes:
    positions = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], dtype="<f4")
    binary = positions.tobytes()
    accessors = [{"bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3", "min": list(lo), "max": list(hi)}]
    views = [{"buffer": 0, "byteOffset": 0, "byteLength": len(binary)}]
    if skin is not None:
        ibm = np.asarray(skin["ibm"], dtype="<f4").T.reshape(-1)  # column-major
        views.append({"buffer": 0, "byteOffset": len(binary), "byteLength": ibm.nbytes})
        accessors.append({"bufferView": 1, "componentType": 5126, "count": 1, "type": "MAT4"})
        binary += ibm.tobytes()
    gltf = {
        "asset": {"version": "2.0", "generator": "pubcast-test"},
        "scene": 0, "scenes": scenes or [{"nodes": [0]}], "nodes": nodes,
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(binary)}],
    }
    if skin is not None:
        gltf["skins"] = [{"joints": skin["joints"], "inverseBindMatrices": 1}]
    if extra:
        gltf.update(extra)
    js = json.dumps(gltf).encode()
    js += b" " * (-len(js) % 4)
    binary += b"\0" * (-len(binary) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
            + struct.pack("<II", len(binary), 0x004E4942) + binary)


def inches(m: float) -> float:
    return m / AI.INCH_M


# ── parsing ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("blob,message", [
    (b"", "too small"),
    (b"not a glb at all, just text bytes", "not a GLB"),
    (struct.pack("<III", 0x46546C67, 1, 20) + b"\0" * 8, "version 1"),
])
def test_malformed_files_are_rejected(blob, message):
    with pytest.raises(AI.GLBError, match=message):
        AI.parse_glb(blob)


def test_truncated_glb_is_rejected():
    data = make_glb([{"mesh": 0}])
    with pytest.raises(AI.GLBError, match="length header"):
        AI.parse_glb(data[:-8])


def test_mesh_without_position_bounds_is_rejected():
    data = make_glb([{"mesh": 0}])
    gltf, binary = AI.parse_glb(data)
    del gltf["accessors"][0]["min"]
    js = json.dumps(gltf).encode(); js += b" " * (-len(js) % 4)
    rebuilt = (struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(binary)) + struct.pack("<II", len(js), 0x4E4F534A)
               + js + struct.pack("<II", len(binary), 0x004E4942) + binary)
    with pytest.raises(AI.GLBError, match="POSITION bounds"):
        AI.measure_glb(rebuilt)


# ── measurement ────────────────────────────────────────────────────────────

def test_plain_mesh_height():
    m = AI.measure_glb(make_glb([{"mesh": 0}]))
    assert m["height_m"] == pytest.approx(1.0) and m["min_y_m"] == pytest.approx(0.0)
    assert not m["skinned"]


def test_nested_scale_rotation_and_translation_are_composed():
    # Parent scales by 2 and lifts 1 m; child lies the 1 m box on its side (rotate 90° about X).
    s = np.sqrt(0.5)
    nodes = [{"children": [1], "scale": [2, 2, 2], "translation": [0, 1, 0]},
             {"mesh": 0, "rotation": [s, 0, 0, s]}]
    m = AI.measure_glb(make_glb(nodes))
    assert m["height_m"] == pytest.approx(0.4, abs=1e-5)      # the 0.2 m depth, doubled, is now vertical
    assert m["depth_m"] == pytest.approx(2.0, abs=1e-5)


def test_matrix_nodes_are_column_major():
    matrix = [3, 0, 0, 0, 0, 3, 0, 0, 0, 0, 3, 0, 0, 0.5, 0, 1]  # uniform ×3, then up 0.5 m
    m = AI.measure_glb(make_glb([{"mesh": 0, "matrix": matrix}]))
    assert m["height_m"] == pytest.approx(3.0) and m["min_y_m"] == pytest.approx(0.5)


def test_skinned_mesh_ignores_node_transform_and_uses_rest_pose():
    # The mesh node claims ×10, which glTF says to ignore for skinned meshes.
    # Joint world ×2 with an identity inverse bind gives a 2 m rest pose.
    nodes = [{"children": [1, 2]}, {"mesh": 0, "skin": 0, "scale": [10, 10, 10]}, {"scale": [2, 2, 2]}]
    m = AI.measure_glb(make_glb(nodes, skin={"joints": [2], "ibm": np.eye(4)}))
    assert m["height_m"] == pytest.approx(2.0) and m["skinned"] and m["joints"] == 1


def test_only_the_default_scene_is_measured():
    nodes = [{"mesh": 0}, {"mesh": 0, "scale": [50, 50, 50]}]
    m = AI.measure_glb(make_glb(nodes, scenes=[{"nodes": [0]}, {"nodes": [1]}]))
    assert m["height_m"] == pytest.approx(1.0)


# ── canonical height (the Godzilla rule) ───────────────────────────────────

def test_correct_height_passes():
    AI.check_canonical_height({"height_m": 68 * AI.INCH_M, "min_y_m": 0.0}, 68)


@pytest.mark.parametrize("height_m", [68 * AI.INCH_M * 1.05, 68 * AI.INCH_M * 0.95, 68 * AI.INCH_M * 100])
def test_wrong_height_is_refused(height_m):
    with pytest.raises(AI.GLBError, match="canonical height"):
        AI.check_canonical_height({"height_m": height_m, "min_y_m": 0.0}, 68)


def test_floating_or_sunken_feet_are_refused():
    with pytest.raises(AI.GLBError, match="off the floor"):
        AI.check_canonical_height({"height_m": 68 * AI.INCH_M, "min_y_m": 0.3}, 68)


# ── real files ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,height_m,joints,clip", [
    ("mh_male.glb", 1.729, 52, "Wave"),
    ("mh_female.glb", 1.591, 52, "Wave"),
    ("husky.glb", 3.207, 49, "AnimalArmature|Walk"),
])
def test_real_rigged_files_measure_as_authored(name, height_m, joints, clip):
    m = AI.measure_glb((FIXTURES / name).read_bytes())
    assert m["height_m"] == pytest.approx(height_m, abs=0.01)
    assert m["skinned"] and m["joints"] == joints and clip in m["animations"]


def test_raw_husky_is_a_godzilla_until_scaled():
    m = AI.measure_glb((FIXTURES / "husky.glb").read_bytes())
    with pytest.raises(AI.GLBError, match="canonical height"):
        AI.check_canonical_height(m, 28)


# ── storage and routes ─────────────────────────────────────────────────────

def standing_glb(height_in: float) -> bytes:
    return make_glb([{"mesh": 0}], hi=(0.2, height_in * AI.INCH_M, 0.1))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("PUBCAST_ENFORCE_AUTH", raising=False)
    app = FastAPI()
    router = AI.create_avatar_import_router(tmp_path)
    app.include_router(router)
    with TestClient(app) as c:
        c.store = router.store
        c.data_dir = tmp_path
        yield c


def post(client, data, *, name="Test", height_in=68, ctype="model/gltf-binary", headers=None):
    return client.post(f"/api/avatars/imports?name={name}&height_in={height_in}&source_format=fbx&source_name=x.fbx",
                       content=data, headers={"Content-Type": ctype, **(headers or {})})


def test_import_list_download_and_manifest_pack(client):
    data = standing_glb(68)
    r = post(client, data, name="Pete Stand-in")
    assert r.status_code == 201, r.text
    avatar = r.json()["avatar"]
    assert avatar["canonical_height_in"] == 68 and avatar["source_format"] == "fbx"
    assert avatar["measured"]["height_m"] == pytest.approx(68 * AI.INCH_M)
    assert [a["id"] for a in client.get("/api/avatars/imports").json()["avatars"]] == [avatar["id"]]
    got = client.get(avatar["url"])
    assert got.status_code == 200 and got.content == data and got.headers["content-type"] == "model/gltf-binary"
    pack = client.store.manifest_pack()
    assert pack["pack_id"] == "imported" and pack["assets"][0]["canonical_height_m"] == pytest.approx(1.7272)


def test_godzilla_upload_is_refused_and_nothing_is_stored(client):
    r = post(client, standing_glb(68 * 30), height_in=68)
    assert r.status_code == 422 and "canonical height" in r.json()["detail"]
    assert client.get("/api/avatars/imports").json()["avatars"] == []
    assert not list((client.data_dir / "avatars" / "imported").glob("*.glb"))


@pytest.mark.parametrize("query,status", [
    ("name=&height_in=68", 400),
    ("name=A&height_in=", 400),
    ("name=A&height_in=tall", 400),
    ("name=A&height_in=2", 422),
    ("name=A&height_in=400", 422),
])
def test_bad_parameters(client, query, status):
    r = client.post(f"/api/avatars/imports?{query}", content=standing_glb(68), headers={"Content-Type": "model/gltf-binary"})
    assert r.status_code == status


def test_non_glb_content_type_is_refused(client):
    assert post(client, standing_glb(68), ctype="application/json").status_code == 415


def test_garbage_body_is_refused(client):
    r = post(client, b"PK\x03\x04 this is a zip, not a glb")
    assert r.status_code == 422 and "GLB" in r.json()["detail"]


@pytest.mark.parametrize("bad_id", ["../index", "..", "UPPER", "a" * 70, "x.glb"])
def test_unsafe_ids_never_touch_the_filesystem(client, bad_id):
    assert client.get(f"/api/avatars/imports/{bad_id}/model.glb").status_code in (400, 404)


def test_canonical_heights_default_and_file_override(client):
    cast = client.get("/api/avatars/canonical-heights").json()["cast"]
    assert {k: v["height_in"] for k, v in cast.items()} == {"sir_purfluous": 74, "pete": 68, "repete": 70}
    path = client.data_dir / "avatars" / "canonical_heights.json"
    path.write_text(json.dumps({"unit": "inches", "cast": {"pete": {"name": "Pete", "height_in": 67}}}))
    assert client.get("/api/avatars/canonical-heights").json()["cast"]["pete"]["height_in"] == 67


def test_index_survives_a_new_store_instance(client):
    avatar = post(client, standing_glb(70), name="RePete Stand-in", height_in=70).json()["avatar"]
    again = AI.AvatarImportStore(client.data_dir)
    assert again.get(avatar["id"])["canonical_height_in"] == 70


def test_delete_is_owner_or_moderator_only(tmp_path, monkeypatch):
    from modules.auth import create_access_token
    monkeypatch.setenv("PUBCAST_ENFORCE_AUTH", "1")
    app = FastAPI()
    router = AI.create_avatar_import_router(tmp_path)
    app.include_router(router)
    owner = {"Authorization": "Bearer " + create_access_token({"sub": "alice", "role": "viewer"})}
    other = {"Authorization": "Bearer " + create_access_token({"sub": "bob", "role": "viewer"})}
    with TestClient(app) as c:
        avatar = post(c, standing_glb(68), headers=owner).json()["avatar"]
        assert c.delete(f"/api/avatars/imports/{avatar['id']}", headers=other).status_code == 403
        assert c.delete(f"/api/avatars/imports/{avatar['id']}", headers=owner).status_code == 200
        assert c.get(avatar["url"]).status_code == 404


def test_main_app_serves_page_routes_and_merges_imported_pack():
    import main
    paths = {r.path for r in main.app.routes}
    assert {"/avatar-import", "/api/avatars/imports", "/api/avatars/canonical-heights"} <= paths
    assert main.BodySizeLimitMiddleware.limit_for("/api/avatars/imports") >= 200 * 1024 * 1024
    assert main.BodySizeLimitMiddleware.limit_for("/api/avatars/me") == 1_048_576
