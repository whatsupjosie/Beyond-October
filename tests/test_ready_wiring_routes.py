def test_menu_coverage_endpoint_is_available(client_no_lifespan):
    response = client_no_lifespan.get("/api/menu/coverage")
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert any(menu["id"] == "help_recovery" for menu in data["menus"])


def test_pub_manager_safe_actions_endpoint_lists_ready_checks(client_no_lifespan):
    response = client_no_lifespan.get("/api/pub-manager/safe-actions")
    assert response.status_code == 200
    data = response.json()
    action_ids = {item["id"] for item in data["safe_actions"]}
    assert "ai.model_slots" in action_ids
    assert "ai.switchblade_status" in action_ids
    assert "runtime.spine_status" in action_ids
    assert "voxel.block_kit_status" in action_ids
    assert "voxel.block_kit_preview" in action_ids


def test_switchblade_route_preview_is_no_model_and_routes_math(client_no_lifespan):
    response = client_no_lifespan.post(
        "/api/switchblade/route-preview",
        json={"role": "auto", "message": "calculate the percent and verify the ratio"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert data["decision"]["slot"] == "background_math"
    assert data["decision"]["mode"] == "auto"


def test_runtime_spine_status_endpoint_imports_ready_modules(client_no_lifespan):
    response = client_no_lifespan.get("/api/runtime-spine/status")
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert data["missing_files"] == []
    assert "RuntimeState" in data["exported"]

def test_voxel_block_kit_status_endpoint_reports_pubblocks(client_no_lifespan):
    response = client_no_lifespan.get("/api/voxel/block-kit/status")
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert data["read_only"] is True
    assert data["base_block_inches"] == 10
    assert data["subdivisions"] == {"full": 1, "half": 2, "quarter": 4}
    assert data["unit_inches"]["quarter"] == 2.5
    assert "guide_grid" in data["builders"]
    assert data["creates_map_rooms"] is False
    assert data["creates_consoles"] is False

def test_voxel_block_kit_preview_endpoint_is_dry_run(client_no_lifespan):
    response = client_no_lifespan.post(
        "/api/voxel/block-kit/preview",
        json={"kind": "stage_floor", "width": 2, "depth": 2, "subdivision": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["read_only"] is True
    assert data["saved"] is False
    assert data["creates_map_rooms"] is False
    assert data["creates_consoles"] is False
    assert data["measurement"]["unit_inches"] == 5.0
    assert data["block_count"] == 16


def test_voxel_block_kit_preview_capabilities_endpoint_is_non_mutating(client_no_lifespan):
    response = client_no_lifespan.get("/api/voxel/block-kit/preview/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert data["read_only"] is True
    assert data["saves_assets"] is False
    assert "adaptive_extension" in data["supported_previews"]