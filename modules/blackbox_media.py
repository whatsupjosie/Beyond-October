"""Dedicated PCM capture sink. Control routes never accept files or serve media.

A capture connection owns one WAV and sample clock. Every acknowledged packet
has been fsynced. Preservation copies exact sample frames into a new WAV; it
never trims or rewrites the original. One process owns a capture directory.
"""
from __future__ import annotations

import math
import json
import os
import threading
import time
import uuid
import wave
from pathlib import Path


class CaptureSink:
    def __init__(self, root: Path, *, sample_rate: int, channels: int):
        if sample_rate not in {16000, 24000, 44100, 48000} or channels not in {1, 2}:
            raise ValueError('Unsupported PCM format')
        self.id = uuid.uuid4().hex
        self.path = root / (self.id + '.wav')
        self.rate, self.channels = sample_rate, channels
        self.frames = 0
        self.started_at = time.time()
        self.last_progress = None
        self.closed = False
        self.error = None
        self._lock = threading.RLock()
        self._file = self.path.open('x+b')
        self._wav = wave.open(self._file, 'wb')
        self._wav.setparams((channels, 2, sample_rate, 0, 'NONE', 'not compressed'))
        self._wav.writeframes(b'')
        self.flush()
        self.path.with_suffix('.json').write_text(json.dumps({
            'capture_id': self.id, 'started_at': self.started_at,
            'sample_rate': self.rate, 'channels': self.channels,
        }), encoding='utf-8')

    @classmethod
    def recover(cls, path):
        meta = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        with wave.open(str(path), 'rb') as src:
            if src.getsampwidth() != 2:
                raise ValueError('Unsupported recovered format')
            obj = cls.__new__(cls)
            obj.id, obj.path = path.stem, path
            obj.rate, obj.channels, obj.frames = src.getframerate(), src.getnchannels(), src.getnframes()
        obj.started_at = float(meta['started_at'])
        obj.last_progress = None
        obj.closed, obj.error = True, None
        obj._lock = threading.RLock()
        return obj

    def flush(self):
        with self._lock:
            if not self.closed:
                self._wav.writeframes(b'')  # refresh RIFF sizes for a readable live snapshot
                self._file.flush()
                os.fsync(self._file.fileno())

    def append(self, pcm: bytes):
        with self._lock:
            if self.closed or self.error:
                raise ValueError('Capture is no longer writable')
            if not pcm or len(pcm) > self.rate * self.channels * 2 * 2 or len(pcm) % (2 * self.channels):
                raise ValueError('Invalid PCM packet size')
            # RIFF/WAV has a 32-bit size field. End cleanly rather than corrupt
            # a marathon recording; the capture client reconnects to a new WAV.
            if self.frames * self.channels * 2 + len(pcm) > 0xFFFF0000:
                raise ValueError('WAV size limit: reconnect capture')
            try:
                self._wav.writeframes(pcm)
                self._file.flush()
                os.fsync(self._file.fileno())
            except Exception as exc:
                self.error = str(exc)
                raise
            self.frames += len(pcm) // (2 * self.channels)
            self.last_progress = time.monotonic()
            return self.frames

    def status(self):
        with self._lock:
            recent = self.last_progress is not None and time.monotonic() - self.last_progress < 5
            state = 'crashed' if self.error or (not self.closed and self.frames and not recent) else (
                'running' if not self.closed and self.frames and recent else 'inactive')
            return {'capture_id': self.id, 'state': state, 'frames': self.frames,
                    'duration_seconds': self.frames / self.rate, 'started_at': self.started_at,
                    'sample_rate': self.rate, 'channels': self.channels}

    def close(self):
        with self._lock:
            if self.closed:
                return
            try:
                self._wav.close()
                self._file.flush()
                os.fsync(self._file.fileno())
            finally:
                self._file.close()
                self.closed = True

    def preserve(self, start: float, end: float, destination: Path):
        if not all(math.isfinite(v) for v in (start, end)) or start < 0 or end <= start:
            raise ValueError('Use a finite increasing range in seconds from capture start')
        with self._lock:
            first, last = round(start * self.rate), round(end * self.rate)
            if last > self.frames or first == last:
                raise ValueError('Range is outside committed capture frames')
            self.flush()
            try:
                with wave.open(str(self.path), 'rb') as src, destination.open('x+b') as target:
                    with wave.open(target, 'wb') as out:
                        out.setparams(src.getparams())
                        src.setpos(first)
                        remaining = last - first
                        while remaining:
                            n = min(remaining, self.rate)
                            data = src.readframes(n)
                            if len(data) != n * self.channels * 2:
                                raise OSError('Source ended before requested range')
                            out.writeframesraw(data)
                            remaining -= n
                    target.flush()
                    os.fsync(target.fileno())
            except Exception:
                destination.unlink(missing_ok=True)
                raise
            return {'frames': last - first, 'start_seconds': first / self.rate,
                    'end_seconds': last / self.rate, 'original_unchanged': True}


class BlackBoxMedia:
    def __init__(self, data_dir: Path):
        self.root = Path(data_dir) / 'blackbox' / 'media'
        self.root.mkdir(parents=True, exist_ok=True)
        self.captures: dict[str, CaptureSink] = {}
        self._lock = threading.RLock()
        for path in sorted(self.root.glob('*.wav'), key=lambda p: p.stat().st_mtime):
            if not path.with_suffix('.json').exists():
                continue  # preserved artifact, not a capture
            try:
                capture = CaptureSink.recover(path)
                self.captures[capture.id] = capture
            except (ValueError, OSError, wave.Error, KeyError):
                continue  # leave damaged source bytes untouched for external inspection

    def start(self, sample_rate: int, channels: int):
        with self._lock:
            if any(not c.closed for c in self.captures.values()):
                raise ValueError('A control-room source is already capturing')
            capture = CaptureSink(self.root, sample_rate=sample_rate, channels=channels)
            self.captures[capture.id] = capture
            return capture

    def status(self):
        with self._lock:
            captures = [c.status() for c in self.captures.values()]
            live = [c for c in captures if not self.captures[c['capture_id']].closed]
            if not live and captures:
                live = captures[-1:]
            state = 'crashed' if any(c['state'] == 'crashed' for c in live) else (
                'running' if any(c['state'] == 'running' for c in live) else 'inactive')
            return {'state': state, 'captures': captures}

    def save(self):
        with self._lock:
            for capture in self.captures.values():
                capture.flush()
            return {'ok': True, 'operation': 'save', 'captures': self.status()['captures']}

    def preserve(self, capture_id: str, start: float, end: float):
        with self._lock:
            capture = self.captures.get(capture_id)
            if capture is None:
                raise ValueError('Unknown capture_id; choose an explicit current-session capture')
            artifact_id = uuid.uuid4().hex
            result = capture.preserve(start, end, self.root / (artifact_id + '.wav'))
            return {'ok': True, 'operation': 'preserve', 'artifact_id': artifact_id,
                    'capture_id': capture_id, **result}

    def close(self):
        with self._lock:
            for capture in self.captures.values():
                capture.close()
