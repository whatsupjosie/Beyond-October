"""Offline experiment contracts; no live archive migration is exercised here."""
import json

import pytest
pytest.importorskip('zstandard')
pytest.importorskip('msgpack')

from blackbox_event_language.schema import REQUIRED_FIELDS,parse_record
from blackbox_decoder import build_known_record_report
from tools.experiments.blackbox_storage_three_way import (
    METHODS,encode,decode,decode_frame,header_of,workload,validate_chain)


@pytest.fixture(scope='module')
def dictionary():
    import zstandard
    return zstandard.train_dictionary(2048,workload(200,101).splitlines(keepends=True)).as_bytes()


@pytest.mark.parametrize('method',METHODS)
def test_exact_bytes_hash_chain_and_human_report_survive_archive(method,dictionary):
    source=workload(40,57)
    archive=encode(source,method,4096,dictionary)
    restored=decode(archive)
    assert restored==source
    validate_chain(restored)
    assert build_known_record_report(restored.decode().splitlines())==build_known_record_report(source.decode().splitlines())


@pytest.mark.parametrize('method',METHODS)
def test_middle_corruption_does_not_destroy_other_frames(method,dictionary):
    source=workload(40,57);archive=bytearray(encode(source,method,4096,dictionary))
    header,start=header_of(archive);middle=len(header['frames'])//2
    entry=header['frames'][middle];archive[start+entry['offset']+entry['size']//2]^=1
    with pytest.raises(Exception):decode_frame(bytes(archive),middle)
    for i in range(len(header['frames'])):
        if i!=middle:assert decode_frame(bytes(archive),i)


@pytest.mark.parametrize('method',METHODS)
def test_incomplete_last_frame_never_counts_as_complete_archive(method,dictionary):
    archive=encode(workload(40,57),method,4096,dictionary)
    header,_=header_of(archive)
    with pytest.raises(Exception):decode(archive[:-5])
    for i in range(len(header['frames'])-1):assert decode_frame(archive[:-5],i)


def test_columnar_preserves_unusual_valid_historical_field_order():
    original=workload(1,57);fields=parse_record(original.decode())
    unusual=('BBX1|'+'|'.join(f'{key}={fields[key]}' for key in reversed(REQUIRED_FIELDS))+'\n').encode()
    assert decode(encode(unusual,'column9',4096))==unusual


def test_dictionary_is_embedded_and_an_incorrect_one_is_rejected(dictionary):
    import struct
    from tools.experiments.blackbox_storage_three_way import MAGIC
    archive=encode(workload(10,57),'zstd9_dict',4096,dictionary)
    header,start=header_of(archive)
    header['dictionary']=''
    modified=json.dumps(header,separators=(',',':')).encode()
    broken=MAGIC+struct.pack('>I',len(modified))+modified+archive[start:]
    with pytest.raises(ValueError,match='Dictionary checksum mismatch'):decode(broken)
