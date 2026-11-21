"""Run explicitly with python -m pytest -qs tools/acceptance/studio_long_take.py.

Set PUBCAST_EVIDENCE_DIR to retain the exported take outside pytest temporary storage.
"""
import json
import os
import subprocess
import time
from pathlib import Path

from tests.test_production25d_browser import (
    production_browser, production_server, recorder_chunks, studio,
    wait_for_actors, wait_for_media_chunk,
)


def test_studio_long_take(studio, tmp_path):
    page, _ = studio
    wait_for_actors(page)
    page.click("#start")
    page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
    page.click("#record")
    page.wait_for_function("PubCast25DStudio.state().recording")
    wait_for_media_chunk(page)
    start = time.monotonic()
    previous = 0
    for minute in range(1, 31):
        while time.monotonic() - start < minute * 60:
            page.wait_for_timeout(1000)
        chunks = recorder_chunks(page)
        print(f"Minute {minute}, {chunks} nonempty chunks", flush=True)
        assert chunks > previous and page.evaluate("PubCast25DStudio.state().recording")
        previous = chunks

    page.click("#recordStop")
    page.wait_for_function("!PubCast25DStudio.state().recording", timeout=120000)
    page.click("#stop")
    page.wait_for_function("!PubCast25DStudio.state().session")
    page.reload()
    page.click("#sessionList button")
    page.wait_for_function("playback.readyState >= 2 && playback.videoWidth === 1280")
    page.evaluate("playback.play()")
    page.wait_for_function("playback.currentTime > .1")
    with page.expect_download(timeout=120000) as pending:
        page.click("#download")
    folder = Path(os.environ.get("PUBCAST_EVIDENCE_DIR", tmp_path))
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / "studio-long-take.webm"
    pending.value.save_as(output)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "packet=pts_time", "-of", "csv=p=0", str(output)],
        capture_output=True, text=True, check=True,
    )
    timestamps = [float(line) for line in probe.stdout.splitlines() if line.strip()]
    duration = max(timestamps) - min(timestamps)
    print(json.dumps({"bytes": output.stat().st_size, "video_packet_span": duration,
                      "packets": len(timestamps), "page_errors": page.problems}), flush=True)
    assert duration >= 1800 and not page.problems
