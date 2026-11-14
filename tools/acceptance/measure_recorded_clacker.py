"""Measure the clacker from encoded Program and reference files from one take."""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np


def starts(mask):
    return np.flatnonzero(mask & ~np.r_[False, mask[:-1]]) if len(mask) else []


def decoded_marks(video, audio):
    timestamps = subprocess.check_output(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
         'frame=best_effort_timestamp_time', '-of', 'json', str(video)], timeout=120,
    )
    times = np.array([float(frame['best_effort_timestamp_time'])
                      for frame in json.loads(timestamps)['frames']])
    pixels = subprocess.check_output(
        ['ffmpeg', '-v', 'error', '-i', str(video), '-an', '-vf', 'crop=42:8:34:28,scale=1:1,setpts=N',
         '-fps_mode', 'passthrough', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'], timeout=120,
    )
    rgb = np.frombuffer(pixels, dtype=np.uint8).reshape(-1, 3).astype(int)
    if len(times) != len(rgb):
        raise ValueError('Decoded video frame count does not match its timestamp count')
    red = (rgb[:, 0] > 180) & (rgb[:, 0] > 2 * rgb[:, 1]) & (rgb[:, 0] > 2 * rgb[:, 2])
    pcm = subprocess.check_output(
        ['ffmpeg', '-v', 'error', '-i', str(audio), '-vn', '-ac', '1',
         '-af', 'aresample=8000:async=1:first_pts=0', '-f', 'f32le', 'pipe:1'], timeout=120,
    )
    samples = np.frombuffer(pcm, dtype='<f4')
    windows = samples[:len(samples) // 8 * 8].reshape(-1, 8)
    pulses = starts(np.sqrt(np.mean(windows ** 2, axis=1)) > .03)
    return times[starts(red)], np.asarray(pulses) / 1000


def measure(video, audio, session, fps):
    take = session['media']
    stem, = [track for track in session['sourceTracks']
             if track['kind'] == 'sync-reference' and track['parentTakeId'] == take['id']]
    if take['syncReferenceId'] != stem['syncReferenceId']:
        raise ValueError('Program and clacker tracks reference different clocks')
    clock, = [entry for entry in session['syncReferences'] if entry['id'] == take['syncReferenceId']]
    interval = clock['intervalUs'] / 1_000_000
    if not np.isfinite(interval) or interval <= 0 or not np.isfinite(fps) or fps <= 0:
        raise ValueError('Clacker interval and export frame rate must be positive and finite')
    video_times, audio_times = decoded_marks(video, audio)
    expected = {mark['sequence'] for mark in clock['audioMarks']}
    expected.update(mark['sequence'] for mark in clock['videoMarks'])
    marks = {sequence: {'audio': [], 'video': []} for sequence in expected}
    # Stop attributing by ordinal when the decoded clock has wandered enough
    # that a nearest-cadence assignment could plausibly belong to another mark.
    attribution_limit = interval / 4
    unattributed = {'audio': [], 'video': []}
    for kind, times, offset in [('audio', audio_times, stem['offsetMs']),
                                ('video', video_times, take['offsetMs'])]:
        for time in times:
            production_time = float(time) + offset / 1000
            sequence = round(production_time / interval)
            if abs(production_time - sequence * interval) > attribution_limit:
                unattributed[kind].append(production_time)
                continue
            marks.setdefault(sequence, {'audio': [], 'video': []})[kind].append(production_time)
    measurements = []
    for sequence, mark in sorted(marks.items()):
        row = {'sequence': sequence, 'expected_in_manifest': sequence in expected, **mark}
        if sequence in expected and len(mark['audio']) == len(mark['video']) == 1:
            row['video_minus_audio_ms'] = (mark['video'][0] - mark['audio'][0]) * 1000
            row['audio_minus_timecode_ms'] = (mark['audio'][0] - sequence * interval) * 1000
            row['video_minus_timecode_ms'] = (mark['video'][0] - sequence * interval) * 1000
        measurements.append(row)
    paired = [row for row in measurements if 'video_minus_audio_ms' in row]
    errors = [abs(row['video_minus_audio_ms']) for row in paired]
    limit = 1000 / fps
    return {
        'reference_interval_seconds': interval, 'audio_detection_window_ms': 1,
        'export_fps': fps, 'one_frame_ms': limit, 'matched': len(paired),
        'expected_in_manifest': len(expected), 'within_one_frame': sum(error <= limit for error in errors),
        'worst_absolute_offset_ms': max(errors, default=None),
        'beginning_middle_end': [paired[i] for i in (0, len(paired) // 2, -1)] if paired else [],
        'missing_audio': [row['sequence'] for row in measurements if row['expected_in_manifest'] and not row['audio']],
        'missing_video': [row['sequence'] for row in measurements if row['expected_in_manifest'] and not row['video']],
        'duplicates': [row['sequence'] for row in measurements if len(row['audio']) > 1 or len(row['video']) > 1],
        'unexpected': [row['sequence'] for row in measurements if not row['expected_in_manifest']],
        'unattributed_seconds': unattributed, 'attribution_limit_seconds': attribution_limit,
        'measurements': measurements,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('program', type=Path)
    parser.add_argument('reference', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--fps', type=float, default=30)
    args = parser.parse_args()
    if not 0 < args.fps <= 240:
        parser.error('--fps must be positive and at most 240')
    print(json.dumps(measure(args.program, args.reference, json.loads(args.manifest.read_text()), args.fps), indent=2))


if __name__ == '__main__':
    main()
