from pathlib import Path


def test_hyperreal_lantern_css_refinement_is_present():
    html = Path("static/pubpartner.html").read_text(encoding="utf-8")
    css = Path("static/pubpartner.css").read_text(encoding="utf-8")
    assert "Hyperreal Lantern Desk" in html
    assert "HYPERREAL UI PROTOTYPE" in html
    # Visual refinement markers: layered surfaces, beveling, texture, and rich preview scene.
    assert "--metal-gradient" in css
    assert "--bevel" in css
    assert "mix-blend-mode:screen" in css
    assert "preview-art::before" in css
    assert "preview-stage::after" in css
    assert "wardrobe-wheel button" in css
    assert "glass" in css
    # Draggable/customizable UI contract from Repair8 must survive the visual pass.
    assert "data-panel=\"conversation\"" in html
    assert "data-panel=\"preview\"" in html
    assert "data-panel=\"wardrobe\"" in html
    assert "Customize Layout" in html
