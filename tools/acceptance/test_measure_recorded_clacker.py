from tools.acceptance import measure_recorded_clacker as clacker


def test_unmatched_and_duplicate_decoded_marks_are_reported(monkeypatch):
    session = {
        'media': {'id': 'program', 'syncReferenceId': 'clock', 'offsetMs': 0},
        'sourceTracks': [{'kind': 'sync-reference', 'parentTakeId': 'program',
                          'syncReferenceId': 'clock', 'offsetMs': 0}],
        'syncReferences': [{'id': 'clock', 'intervalUs': 15_000_000,
                            'audioMarks': [{'sequence': n} for n in (1, 2, 3)],
                            'videoMarks': [{'sequence': n} for n in (1, 2, 3)]}],
    }
    monkeypatch.setattr(clacker, 'decoded_marks',
                        lambda *_: ([15.012, 15.125, 35, 45.025, 60], [15, 30, 45]))
    result = clacker.measure(None, None, session, 30)
    assert result['duplicates'] == [1]
    assert result['missing_video'] == [2]
    assert result['unattributed_seconds']['video'] == [35]
    assert result['unexpected'] == [4]
    assert result['matched'] == result['within_one_frame'] == 1
