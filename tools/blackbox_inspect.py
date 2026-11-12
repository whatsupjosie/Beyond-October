"""Read-only offline verification of coded ledgers and their PCM packet receipts.

Run with the host stopped for a stable snapshot. No player-facing review API.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from blackbox_event_language.schema import decode_record
from blackbox_recorder import AppendOnlyBlackBoxRecorder
from modules.blackbox_media import CaptureSink


def _chat_signature(room, author, text, timestamp):
    if not isinstance(text, str):
        raise ValueError('Chat text is not a string')
    return (str(room), str(author), hashlib.sha256(text.encode('utf-8')).hexdigest(), str(timestamp))


def _inspect_chat(data_dir, witnesses):
    result = {'checked':0, 'missing':0, 'unarchived':0, 'mismatched':0, 'duplicates':0,
              'unverifiable':0, 'errors':[]}
    seen = set()
    for path in sorted((Path(data_dir)/'logs').glob('*.jsonl')):
        try:
            if path.is_symlink():raise ValueError('Chat archive symlink refused')
            with path.open(encoding='utf-8') as source:
                for line in source:
                    if not line.strip():continue
                    entry = json.loads(line)
                    if not isinstance(entry, dict):raise ValueError('Chat archive entry is not an object')
                    message_id = entry.get('message_id')
                    if not isinstance(message_id, str) or not message_id:
                        result['unverifiable'] += 1
                        continue
                    key = (path.stem, message_id)
                    if key in seen:
                        result['duplicates'] += 1
                        continue
                    seen.add(key)
                    result['checked'] += 1
                    candidates = witnesses.get(key, [])
                    if not candidates:
                        result['missing'] += 1
                    elif len(candidates) > 1:
                        result['duplicates'] += 1
                    signature = _chat_signature(entry.get('room'), entry.get('user_id'),
                                                entry.get('text'), entry.get('t'))
                    if candidates and (entry.get('room') != path.stem or any(c != signature for c in candidates)):
                        result['mismatched'] += 1
        except (OSError, ValueError, UnicodeError) as error:
            result['errors'].append({'file':path.name, 'error_type':type(error).__name__})
    result['unarchived'] = len(set(witnesses) - seen)
    return result


def inspect(data_dir):
    root = Path(data_dir) / 'blackbox'
    report = {'schema':'pubcast-blackbox-audit/1', 'ok':True, 'coverage_complete':True,
              'ledgers':[], 'captures':[], 'preserved':[], 'uncatalogued_wavs':[],
              'known_failed_events':0}
    if not root.is_dir():
        return {**report, 'ok':False, 'coverage_complete':False, 'error':'Blackbox directory is absent'}
    receipts = {}
    preserved = {}
    chat_witnesses = {}
    for path in sorted(root.glob('*.bbx')):
        entry = {'file':path.name, 'ok':False}
        try:
            if path.is_symlink():raise ValueError('Ledger symlink refused')
            recorder = AppendOnlyBlackBoxRecorder(path, path.stem)
            check = recorder.verify()
            entry.update(ok=check.ok and check.checked > 0, checked=check.checked, errors=check.errors)
            if check.ok:
                with path.open(encoding='utf-8') as source:
                    for line in source:
                        if not line.strip():continue
                        decoded = decode_record(line)
                        event = decoded['payload']
                        if event.get('event_type') == 'capture.chunk_committed':
                            receipts.setdefault(event['capture_id'], []).append(event)
                        elif event.get('event_type') == 'blackbox.preserved':
                            preserved[event['artifact_id']] = event
                        elif event.get('event_type') == 'runtime.coverage_gap':
                            report['known_failed_events'] += int(event['failed_events'])
                        elif event.get('event_type') == 'chat.message' and event.get('message_id'):
                            details = json.loads(event['data_json']) if 'data_json' in event else event
                            if not isinstance(details, dict):
                                raise ValueError('Chat receipt data is not an object')
                            key = (str(details.get('room')), str(details.get('message_id')))
                            chat_witnesses.setdefault(key, []).append(_chat_signature(
                                details.get('room'), decoded['actor'], details.get('text'), details.get('t')))
        except (OSError, ValueError, UnicodeError, KeyError, TypeError) as error:
            entry['ok'] = False
            entry['error'] = str(error)
        report['ledgers'].append(entry)
        report['ok'] &= entry['ok']
    if not report['ledgers']:
        report['ok'] = False
    for path in sorted((root/'media').glob('*.wav')):
        if not path.with_suffix('.json').exists():
            receipt = preserved.pop(path.stem, None)
            if receipt is not None:
                entry = {'artifact_id':path.stem, 'ok':False}
                try:
                    if path.is_symlink():raise ValueError('Media symlink refused')
                    if CaptureSink.digest(path) != receipt.get('sha256'):
                        raise ValueError('Preserved WAV does not match its ledger checksum')
                    with wave.open(str(path), 'rb') as audio:
                        if audio.getnframes() != int(receipt['frames']):
                            raise ValueError('Preserved WAV frame count mismatch')
                    entry['ok'] = True
                except (OSError, ValueError, KeyError, EOFError, wave.Error) as error:
                    entry['error'] = str(error)
                report['preserved'].append(entry)
                report['ok'] &= entry['ok']
                continue
            report['uncatalogued_wavs'].append(path.name)
            report['coverage_complete'] = False
            continue  # Existing preserve copies have no capture sidecar.
        entry = {'capture_id':path.stem, 'ok':False, 'coverage_complete':False}
        try:
            capture = CaptureSink.recover(path)
            checked = 0; next_frame = 0
            with wave.open(str(path), 'rb') as audio:
                for receipt in sorted(receipts.get(capture.id, []), key=lambda r:int(r['first_frame'])):
                    first, count = int(receipt['first_frame']), int(receipt['frames'])
                    if first != next_frame or not 0 < count <= capture.rate*2 or first+count > capture.frames:
                        raise ValueError('PCM receipt ranges are not continuous committed frames')
                    audio.setpos(first)
                    data = audio.readframes(count)
                    if len(data) != count*capture.channels*2 or hashlib.sha256(data).hexdigest() != receipt['sha256']:
                        raise ValueError('PCM bytes do not match the durable packet receipt')
                    checked += 1; next_frame += count
            entry.update(capture.status(), ok=True, packet_receipts_checked=checked,
                         witnessed_frames=next_frame,
                         coverage_complete=next_frame==capture.frames and not capture.interrupted)
        except (OSError, ValueError, KeyError, TypeError, EOFError, wave.Error) as error:
            entry['error'] = str(error)
        report['captures'].append(entry)
        report['ok'] &= entry['ok']
        report['coverage_complete'] &= entry['coverage_complete']
    captured = {entry['capture_id'] for entry in report['captures']}
    missing = sorted(set(receipts) - captured)
    if missing or preserved:
        report.update(ok=False, coverage_complete=False,
                      missing_captures=missing, missing_preserved=sorted(preserved))
    report['chat'] = _inspect_chat(data_dir, chat_witnesses)
    chat = report['chat']
    if chat['errors'] or chat['mismatched'] or chat['duplicates'] or chat['unarchived']:
        report['ok'] = False
    if (not report['ok'] or report['known_failed_events'] or chat['missing'] or
            chat['unverifiable']):
        report['coverage_complete'] = False
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.data_dir)
    print(json.dumps(report, indent=2))
    return 0 if report['ok'] and report['coverage_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
