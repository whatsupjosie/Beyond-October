from pathlib import Path


def test_relationship_review_controls_are_wired():
    js = Path("static/pubpartner.js").read_text(encoding="utf-8")
    css = Path("static/pubpartner.css").read_text(encoding="utf-8")
    assert "reviewLesson" in js
    assert "dataset.lessonAction" in js
    assert "/api/pubpartner/relationship/lessons/" in js
    assert ".lesson-review-actions" in css
