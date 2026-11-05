"""Measure the recorded reference waveform against actual encoded red video marks."""
import json
import subprocess

import numpy as np

from tests.test_production25d_browser import production_browser, production_server, studio, wait_for_actors
from tests.test_participant_audio_browser import bytes_for, decode


def groups(mask):
    indices = np.flatnonzero(mask)
    return [group for group in np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1) if len(group)]


def test_recorded_clacker_is_separate_silent_in_program_and_aligned_to_video(studio, tmp_path):
    page, _ = studio
    wait_for_actors(page)
    page.click('#start')
    page.click('#record')
    page.wait_for_function('PubCast25DStudio.state().journal?.chunks>=31', timeout=45000)
    page.click('#recordStop')
    page.wait_for_function('!PubCast25DStudio.state().recording', timeout=15000)
    session = page.evaluate('async()=>(await PubCast25DStore.list())[0]')
    (tmp_path / 'session.json').write_text(json.dumps(session, indent=2))
    references = [s for s in session['sourceTracks'] if s['kind'] == 'sync-reference']
    assert len(references) == 1
    reference = references[0]
    assert not reference['incomplete'] and reference['parentTakeId'] == session['media']['id']
    assert session['syncReferences'][0]['intervalUs'] == 15000000
    assert session['syncReferences'][0]['crossDeviceAlignment'] == 'unmeasured'
    marks = session['syncReferences'][0]['audioMarks']
    assert len(marks) >= 2
    for before, after in zip(marks, marks[1:]):
        assert after['frame'] - before['frame'] == 15 * session['syncReferences'][0]['sampleRate']
    assert len(session['syncReferences'][0]['videoMarks']) >= 2

    video = tmp_path / 'program.webm'
    audio = tmp_path / 'reference.webm'
    video.write_bytes(bytes_for(page, session['id'], session['media']['id']))
    audio.write_bytes(bytes_for(page, session['id'], reference['id']))
    program_pcm = decode(video)
    assert np.sqrt(np.mean(program_pcm ** 2)) < .001  # no reference leakage into Program
    samples = decode(audio)
    windows = samples[:len(samples)//480*480].reshape(-1, 480)
    pulses = groups(np.sqrt(np.mean(windows ** 2, axis=1)) > .03)
    audio_times = [float(g[0]) / 100 for g in pulses]
    assert len(audio_times) == 2
    assert abs(audio_times[1] - audio_times[0] - 15) <= .02

    frames = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'csv=p=0', str(video)],
        capture_output=True, text=True, check=True, timeout=30).stdout
    timestamps = [float(line.strip().strip(',')) for line in frames.splitlines() if line.strip().strip(',')]
    pixels = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-an',
        '-vf', 'crop=42:8:34:28,scale=1:1', '-fps_mode', 'passthrough',
        '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'],
        capture_output=True, check=True, timeout=30).stdout
    rgb = np.frombuffer(pixels, dtype=np.uint8).reshape(-1, 3).astype(int)
    assert len(rgb) == len(timestamps)
    flashes = groups((rgb[:, 0] > 180) & (rgb[:, 0] > rgb[:, 1] * 2) & (rgb[:, 0] > rgb[:, 2] * 2))
    video_times = [timestamps[g[0]] for g in flashes]
    assert len(video_times) == 2
    audio_on_production = [t + reference['offsetMs']/1000 for t in audio_times]
    video_on_production = [t + session['media']['offsetMs']/1000 for t in video_times]
    offsets = [v-a for v, a in zip(video_on_production, audio_on_production)]
    (tmp_path / 'measured-clacker.json').write_text(json.dumps({
        'audio_seconds':audio_on_production, 'video_seconds':video_on_production,
        'video_minus_reference_seconds':offsets,
        'scope':'one Linux Chromium shared audio clock; other devices unmeasured'
    }, indent=2))
    assert max(abs(offset) for offset in offsets) < .25, offsets
    assert page.locator('#sessionList button').filter(has_text='SYNC:').count() == 1
    assert page.problems == []


def test_stopped_audio_clock_preserves_incomplete_takes_and_can_restart(studio):
    page, _ = studio
    wait_for_actors(page)
    page.click('#start'); page.click('#record')
    page.wait_for_function('PubCast25DStudio.state().journal?.chunks>=2')
    page.evaluate('PubcastProgramAudio.context.suspend()')
    page.wait_for_function('!PubCast25DStudio.state().recording')
    session = page.evaluate('async()=>(await PubCast25DStore.list())[0]')
    assert session['media']['incomplete']
    assert session['sourceTracks'][0]['incomplete']
    assert 'audio clock stopped' in page.locator('#alert').inner_text()
    page.evaluate('PubcastProgramAudio.context.resume()')
    page.click('#record')
    page.wait_for_function('PubCast25DStudio.state().journal?.chunks>=2')
    page.click('#recordStop')
    page.wait_for_function('!PubCast25DStudio.state().recording')
    session = page.evaluate('async()=>(await PubCast25DStore.list())[0]')
    assert len(session['recordings']) == 2
    assert session['recordings'][0]['incomplete'] and not session['recordings'][1]['incomplete']
    assert len(session['sourceTracks']) == 2
    assert len(session['syncReferences']) == 2
    assert len({t['syncReferenceId'] for t in session['recordings']}) == 2
    assert {t['syncReferenceId'] for t in session['recordings']} == {r['id'] for r in session['syncReferences']}
    assert sum(bool(s['incomplete']) for s in session['sourceTracks']) == 1
