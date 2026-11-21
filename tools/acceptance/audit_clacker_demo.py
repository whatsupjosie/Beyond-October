"""Reproduce and verify the seven-second 30 fps clacker demonstration."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np

START = 61
DURATION = 7
FPS = 30
RATE = 48_000
CROP = 'crop=42:8:34:28'


def decode(path, *args):
    return subprocess.check_output(
        ['ffmpeg', '-v', 'error', '-i', str(path), *args, 'pipe:1'], timeout=60,
    )


def audio(path, track):
    return np.frombuffer(decode(path, '-map', f'0:a:{track}', '-ac', '1', '-ar',
                                str(RATE), '-f', 'f32le'), dtype='<f4')


def blips(samples):
    windows = samples[:len(samples) // 48 * 48].reshape(-1, 48)
    active = np.sqrt(np.mean(windows**2, axis=1)) > .03
    return np.flatnonzero(active & ~np.r_[False, active[:-1]])


def crop_frame_numbers(path):
    data = decode(path, '-an', '-vf', CROP + ',scale=1:1',
                  '-pix_fmt', 'rgb24', '-f', 'rawvideo')
    r, g, b = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).astype(int).T
    return np.flatnonzero((r > 180) & (r > 2 * g) & (r > 2 * b))


def frames(path, start=None, duration=None):
    selection = [] if start is None else ['-ss', str(start), '-t', str(duration)]
    data = decode(path, *selection, '-an', '-vf', 'scale=160:90',
                  '-fps_mode', 'passthrough', '-pix_fmt', 'rgb24', '-f', 'rawvideo')
    return np.frombuffer(data, dtype=np.uint8).reshape(-1, 90, 160, 3).astype(np.int16)


def verify(video, program, evidence, session):
    probe = subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_entries',
         'stream=codec_type,avg_frame_rate,start_time:stream_tags=handler_name:stream_disposition=default',
         '-of', 'json', str(video)], timeout=60,
    )
    picture, *tracks = json.loads(probe)['streams']
    if picture['codec_type'] != 'video' or picture['avg_frame_rate'] != f'{FPS}/1':
        raise ValueError('Demo video is not 30 fps')
    names = ['Preview - Program and clacker', 'Program only', 'Clacker reference']
    if ([track.get('tags', {}).get('handler_name') for track in tracks] != names
            or [track['disposition']['default'] for track in tracks] != [1, 0, 0]
            or any(track['codec_type'] != 'audio' for track in tracks)
            or any(float(stream['start_time']) != 0 for stream in [picture, *tracks])):
        raise ValueError('Unexpected demo track layout, default track or timeline origin')

    mark = crop_frame_numbers(video)
    if len(mark) != 7 or not np.all(np.diff(mark) == 1):
        raise ValueError('Expected one contiguous seven-frame red flash')
    preview, clean, reference = [audio(video, i) for i in range(3)]
    starts = blips(reference)
    if len(starts) != 1:
        raise ValueError(f'Expected one isolated reference pulse, found {len(starts)}')
    onset_ms = int(starts[0])
    flash_ms = float(mark[0] * 1000 / FPS)
    if abs(onset_ms - flash_ms) > 1000 / FPS:
        raise ValueError('Flash and isolated blip differ by more than one frame')

    # Measure the actual 1 kHz tone during the decoded pulse, on each output track.
    low = RATE * (onset_ms + 4) // 1000
    span = RATE // 25
    kernel = np.exp(-2j * np.pi * 1000 * np.arange(span) / RATE)
    levels = [float(abs(track[low:low + span] @ kernel) / span)
              for track in (preview, clean, reference)]
    if min(levels[0], levels[2]) < .08 or levels[1] > .005:
        raise ValueError('Reference pulse missing from preview or leaked into clean Program')

    decoded = frames(video)
    if len(decoded) != FPS * DURATION:
        raise ValueError('Unexpected demo frame count')
    # Compare pixels outside the clacker crop to the recorded shots on either side.
    before = frames(program, START + 2, .5)[-1]
    after = frames(program, START + 4, .5)[0]
    region = np.s_[10:, :, :]
    score = np.mean(np.abs(decoded[:, 10:] - before[region]), axis=(1, 2, 3))
    score -= np.mean(np.abs(decoded[:, 10:] - after[region]), axis=(1, 2, 3))
    cuts = np.flatnonzero((score[1:] > 0) & (score[:-1] < 0)) + 1
    if len(cuts) != 1:
        raise ValueError('Export does not contain exactly one wide-to-anchor transition')

    # Source timestamps and shot detection share one decode. Keep the original PTS.
    probe = subprocess.run(
        ['ffmpeg', '-hide_banner', '-ss', str(START), '-i', str(program), '-t', str(DURATION),
         '-an', '-vf', 'scale=160:90,format=rgb24,showinfo', '-fps_mode', 'passthrough',
         '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'], capture_output=True, check=True, timeout=60,
    )
    source = np.frombuffer(probe.stdout, np.uint8).reshape(-1, 90, 160, 3).astype(np.int16)
    pts = [float(t) for t in re.findall(rb'pts_time:([-\d.]+)', probe.stderr)][:len(source)]
    if len(source) != len(pts):
        raise ValueError('Source frame bytes and decoder timestamps disagree')
    source_score = np.mean(np.abs(source[:, 10:] - before[region]), axis=(1, 2, 3))
    source_score -= np.mean(np.abs(source[:, 10:] - after[region]), axis=(1, 2, 3))
    crossings = np.flatnonzero((source_score[1:] > 0) & (source_score[:-1] < 0)) + 1
    if len(crossings) != 1:
        raise ValueError('Source does not contain exactly one wide-to-anchor transition')
    source_cut = pts[crossings[0]]
    cut = float(cuts[0] / FPS)
    if abs(source_cut - cut) > 1 / FPS:
        raise ValueError('Export moved the visible source cut by more than one frame')
    event, = [event for event in session['events'] if event['type'] == 'camera.cut'
              and START <= (event['offsetMs']-session['media']['offsetMs']) / 1000 < START+DURATION]
    logged_cut = (event['offsetMs']-session['media']['offsetMs']) / 1000 - START
    return dict(flash_ms=flash_ms, blip_ms=onset_ms, visible_export_cut_seconds=cut,
                visible_source_cut_seconds=source_cut, logged_cut_seconds=logged_cut,
                logged_cut_to_visible_source_ms=round((source_cut - logged_cut) * 1000, 3),
                track_tone_amplitudes=levels, input_hashes=evidence)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('take_directory', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    program = args.take_directory / 'endurance.webm'
    reference = args.take_directory / 'clacker-reference.webm'
    session = json.loads((args.take_directory / 'session-manifest.json').read_text())
    report = json.loads((args.take_directory / 'endurance.json').read_text())
    if session != report['session']:
        raise ValueError('Session manifest differs from the endurance report')
    hashes = {}
    for file, key in ((program, 'media_sha256'), (reference, 'clacker_sha256')):
        with file.open('rb') as stream:
            hashes[file.name] = hashlib.file_digest(stream, 'sha256').hexdigest()
        if hashes[file.name] != report[key]:
            raise ValueError(f'SHA-256 mismatch for {file.name}')
    stem, = [track for track in session['sourceTracks']
             if track['kind'] == 'sync-reference' and track['parentTakeId'] == session['media']['id']]
    if stem.get('incomplete') or session['media'].get('incomplete'):
        raise ValueError('Demo requires complete source tracks')
    if stem['offsetMs'] != session['media']['offsetMs']:
        raise ValueError('This demo requires Program and reference with the same capture offset')

    if not args.verify_only:
        pcm = subprocess.check_output(
            ['ffmpeg', '-v', 'error', '-ss', str(START), '-i', str(reference), '-t',
             str(DURATION), '-af', 'aresample=48000:async=1:first_pts=0',
             '-ac', '1', '-f', 'f32le', 'pipe:1'], timeout=60,
        )
        onset, = blips(np.frombuffer(pcm, dtype='<f4'))
        frame = round(onset * FPS / 1000)
        filters = (
            f"[0:v]fps={FPS}:start_time=0:round=near,"
            "drawbox=x=34:y=28:w=42:h=8:color=0x171520:t=fill,"
            f"drawbox=x=34:y=28:w=42:h=8:color=0xff2020:t=fill:enable='between(n,{frame},{frame+6})'[v];"
            "[0:a]aresample=48000:async=1:first_pts=0,asplit=2[program][p];"
            "[1:a]aresample=48000:async=1:first_pts=0,asplit=2[reference][r];"
            "[p][r]amix=inputs=2:normalize=0[mix]"
        )
        subprocess.run(
            ['ffmpeg', '-v', 'error', '-n', '-ss', str(START), '-i', str(program),
             '-ss', str(START), '-i', str(reference), '-filter_complex', filters,
             '-map', '[v]', '-map', '[mix]', '-map', '[program]', '-map', '[reference]',
             '-t', str(DURATION), '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
             '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k',
             '-metadata:s:a:0', 'handler_name=Preview - Program and clacker',
             '-metadata:s:a:1', 'handler_name=Program only',
             '-metadata:s:a:2', 'handler_name=Clacker reference',
             '-disposition:a:0', 'default', '-disposition:a:1', '0', '-disposition:a:2', '0',
             '-movflags', '+faststart', str(args.output)], check=True, timeout=60,
        )
    print(json.dumps(verify(args.output, program, hashes, session), indent=2))


if __name__ == '__main__':
    main()
