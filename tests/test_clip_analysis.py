import shutil, subprocess
import pytest
from modules import clip_analysis as ca

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")


def _make(path, vf="", dur=6, audio="sine=frequency=440:duration=6"):
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=24:duration={dur}",
           "-f", "lavfi", "-i", audio]
    if vf:
        cmd += ["-vf", vf]
    cmd += ["-shortest", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, check=True)


def test_blurred_clip_measures_softer_than_sharp(tmp_path):
    sharp, soft = tmp_path / "s.mp4", tmp_path / "b.mp4"
    _make(sharp); _make(soft, vf="boxblur=8:2")
    s = ca.analyze_technical(sharp)["video"]["sharpness_median"]
    b = ca.analyze_technical(soft)["video"]["sharpness_median"]
    assert b < 0.5 * s


def test_hard_cut_detected(tmp_path):
    a, b, out = tmp_path / "a.mp4", tmp_path / "b.mp4", tmp_path / "c.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:size=640x360:rate=24:duration=3", "-pix_fmt", "yuv420p", str(a)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=white:size=640x360:rate=24:duration=3", "-pix_fmt", "yuv420p", str(b)], check=True)
    lst = tmp_path / "l.txt"; lst.write_text(f"file '{a}'\nfile '{b}'\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True)
    cuts = ca.analyze_technical(out)["video"]["hard_cuts_at_s"]
    assert len(cuts) == 1 and abs(cuts[0] - 3.0) < 0.5


def test_no_cut_in_continuous_clip(tmp_path):
    p = tmp_path / "x.mp4"; _make(p)
    assert ca.analyze_technical(p)["video"]["hard_cuts_at_s"] == []


def test_noisy_audio_flagged(tmp_path):
    p = tmp_path / "n.mp4"; _make(p, audio="anoisesrc=color=white:amplitude=0.3:duration=6")
    r = ca.analyze_technical(p)
    assert any(f["area"] == "audio" for f in r["findings"])


def test_report_states_limits(tmp_path):
    p = tmp_path / "x.mp4"; _make(p)
    text = ca.render_as_repete(ca.analyze_technical(p))
    assert "Dutch angle" in text and "180" in text


def test_rejects_non_media(tmp_path):
    p = tmp_path / "x.txt"; p.write_text("hello")
    with pytest.raises(ca.ClipAnalysisError):
        ca.analyze_technical(p)


def test_missing_file():
    with pytest.raises(ca.ClipAnalysisError):
        ca.analyze_technical("/nonexistent.mp4")
