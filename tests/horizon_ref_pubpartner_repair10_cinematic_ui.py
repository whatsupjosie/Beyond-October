from pathlib import Path


def test_repair10_cinematic_visual_polish_contract_survives():
    html = Path("static/pubpartner.html").read_text(encoding="utf-8")
    css = Path("static/pubpartner.css").read_text(encoding="utf-8")
    js = Path("static/pubpartner.js").read_text(encoding="utf-8")

    assert "Cinematic Hyperreal Lantern Desk" in html
    assert "CINEMATIC POLISH" in html
    assert "ambient-lantern" in html
    assert "notif-chip" in html

    # Visual target markers from the uploaded references:
    # smoky glass, brass/copper bevels, lantern glow, circular wardrobe, fan menu, cinematic preview.
    for marker in [
        "--metal-gradient",
        "--bevel",
        "mix-blend-mode:screen",
        "backdrop-filter:blur",
        "radial-gradient(circle",
        "clip-path:polygon",
        "clip-path:circle",
        "preview-art::before",
        "preview-art::after",
        "preview-stage::after",
        "wardrobe-wheel button",
        "fan-menu button:nth-child",
    ]:
        assert marker in css

    # Customizable/rearrangeable contract must remain.
    assert "data-panel=\"conversation\"" in html
    assert "data-panel=\"preview\"" in html
    assert "data-panel=\"wardrobe\"" in html
    assert "Customize Layout" in html
    assert "localStorage" in js
    assert "pubpartner.lanternDesk.v2.cinematic" in js
    assert "enablePanelFocus" in js
    assert "/api/pubpartner/turns/live" in js
