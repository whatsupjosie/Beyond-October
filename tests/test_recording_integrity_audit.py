"""Prove media hashes, rather than lengths or ZIP CRC, detect corrupted exports."""
import importlib.util
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

from modules import recording as module
from modules.cameras import create_default_cameras
from tests.test_recording_portable_bundle import recording


def test_same_length_corruption_is_rejected_and_hash_mutation_is_detected(tmp_path,monkeypatch):
    source_service,session,source=recording(tmp_path)
    monkeypatch.setattr(source_service,'_find_ffmpeg',lambda:None)
    archive=source_service.export_session(session.session_id,container=module.ContainerFormat.MP4)
    altered=tmp_path/'same-length-corruption.zip';changed=0
    with ZipFile(archive) as original,ZipFile(altered,'w') as output:
        for entry in original.infolist():
            content=original.read(entry)
            if entry.filename.startswith('media/'):
                content=content[:-1]+bytes([content[-1]^1]);changed+=1
                assert len(content)==entry.file_size
            output.writestr(entry,content)  # recalculates ZIP CRC; length still matches
    assert changed==1
    target=module.create_recording_service(tmp_path/'normal',create_default_cameras())
    def reject(service):
        with pytest.raises(ValueError,match='integrity'):
            service.import_session(altered)
    reject(target)
    assert target.list_sessions()==[] and not (target.recordings_dir/session.session_id).exists()
    assert source.read_bytes()[-1:]==b'\x00'

    # Mutation lives in a separate in-memory module: production files are frozen.
    # If hash enforcement is removed, this exact rejection assertion must fail.
    code=Path(module.__file__).read_text();needle='spec.get("sha256") != digest.hexdigest() or '
    assert code.count(needle)==1
    name='modules.recording_audit_mutant'
    spec=importlib.util.spec_from_loader(name,loader=None)
    mutant=importlib.util.module_from_spec(spec);monkeypatch.setitem(sys.modules,name,mutant)
    exec(compile(code.replace(needle,''),module.__file__+' [hash mutation]','exec'),mutant.__dict__)
    weak=mutant.create_recording_service(tmp_path/'mutant',create_default_cameras())
    with pytest.raises(pytest.fail.Exception,match='DID NOT RAISE'):
        reject(weak)
