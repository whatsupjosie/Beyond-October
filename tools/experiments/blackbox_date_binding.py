"""Isolated date/password binding experiment. NOT a production archive format.

Uses real Argon2id, AES-256-GCM and optional Ed25519 signatures. No changes to
PubCast passwords, live files, retention rules or archive readers.
"""
from __future__ import annotations
import argparse
import base64
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import cryptography
import zstandard
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.exceptions import InvalidTag,InvalidSignature

MAGIC=b'BBXDATE1'
PARAMS={'algorithm':'argon2id','memory_kib':65536,'iterations':3,'lanes':4,'length':32}
MAX_RAW=16*1024*1024


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def validate_date(created):
    if not isinstance(created,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z',created):
        raise ValueError('Mandatory canonical UTC creation timestamp missing or malformed')
    datetime.fromisoformat(created.replace('Z','+00:00'))


def derive(password,created,salt):
    validate_date(created)
    if not isinstance(password,str) or not password:raise ValueError('Use any nonempty password')
    # Length-delimited JSON avoids concatenation ambiguity. Date is PUBLIC,
    # not extra password entropy. A new KDF object is required for each derive.
    material=canonical(['pubcast-date-binding-experiment/1',password,created])
    return Argon2id(salt=salt,length=32,iterations=3,lanes=4,memory_cost=65536).derive(material)


def envelope(header,ciphertext,signature=b''):
    wire=canonical(header)
    return MAGIC+struct.pack('>I',len(wire))+wire+ciphertext+signature


def _no_duplicate_keys(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate header field')
        result[key]=value
    return result


def parts(blob):
    if blob[:8]!=MAGIC or len(blob)<12:raise ValueError('Invalid date-binding envelope')
    length=struct.unpack('>I',blob[8:12])[0]
    if not 1<=length<=4096 or len(blob)<12+length+16:raise ValueError('Truncated or excessive header')
    wire=blob[12:12+length]
    header=json.loads(wire,object_pairs_hook=_no_duplicate_keys)
    if not isinstance(header,dict):raise ValueError('Header must be an object')
    validate_date(header.get('original_created_at'))
    if header.get('schema')!='date-binding-experiment/1' or header.get('kdf')!=PARAMS:
        raise ValueError('Unsupported fixed test format or KDF parameters')
    if type(header.get('signed')) is not bool:raise ValueError('Invalid signature flag')
    salt=base64.b64decode(header['salt'],validate=True)
    nonce=base64.b64decode(header['nonce'],validate=True)
    if len(salt)!=16 or len(nonce)!=12:raise ValueError('Invalid salt or nonce')
    if type(header.get('raw_size')) is not int or not 0<=header['raw_size']<=MAX_RAW:
        raise ValueError('Invalid plaintext size')
    signature=blob[-64:] if header['signed'] else b''
    ciphertext=blob[12+length:-64] if header['signed'] else blob[12+length:]
    if len(ciphertext)<16:raise ValueError('Truncated authenticated ciphertext')
    return header,wire,ciphertext,signature,salt,nonce


def seal(raw,password,created,signer=None):
    validate_date(created)
    if len(raw)>MAX_RAW:raise ValueError('Experiment payload limit exceeded')
    salt=os.urandom(16);nonce=os.urandom(12)
    header={'schema':'date-binding-experiment/1','original_created_at':created,
        'file_id':os.urandom(16).hex(),'salt':base64.b64encode(salt).decode(),
        'nonce':base64.b64encode(nonce).decode(),'kdf':PARAMS,'signed':signer is not None,
        'compression':'zstd3','raw_size':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest()}
    key=derive(password,created,salt)
    compressed=zstandard.ZstdCompressor(level=3,write_checksum=True).compress(raw)
    ciphertext=AESGCM(key).encrypt(nonce,compressed,canonical(header))
    unsigned=envelope(header,ciphertext)
    return unsigned+signer.sign(unsigned) if signer is not None else unsigned


def verify_signature(blob,trusted_public_key):
    header,wire,ciphertext,signature,_,_=parts(blob)
    if not header['signed'] or trusted_public_key is None:raise ValueError('Trusted independent signature required')
    # The trusted public key comes from OUTSIDE the supplied archive.
    trusted_public_key.verify(signature,blob[:-64])
    return header


def unlock(blob,password,trusted_public_key=None,require_signed=False):
    header,wire,ciphertext,signature,salt,nonce=parts(blob)
    if header['signed'] or require_signed:verify_signature(blob,trusted_public_key)
    key=derive(password,header['original_created_at'],salt)
    compressed=AESGCM(key).decrypt(nonce,ciphertext,wire)
    if header['compression']!='zstd3':raise ValueError('Unsupported compression')
    if zstandard.frame_content_size(compressed)!=header['raw_size']:raise ValueError('Unexpected decompression size')
    raw=zstandard.ZstdDecompressor(max_window_size=16384).decompress(
        compressed,max_output_size=MAX_RAW,allow_extra_data=False)
    if len(raw)!=header['raw_size'] or hashlib.sha256(raw).hexdigest()!=header['raw_sha256']:
        raise ValueError('Restored plaintext mismatch')
    return raw


def change_header(blob,**changes):
    header,_,ciphertext,signature,_,_=parts(blob)
    header.update(changes)
    return envelope(header,ciphertext,signature)


def study(out):
    from tools.experiments.blackbox_storage_three_way import workload,validate_chain
    raw=workload(64,203)
    created='2026-05-01T12:00:00.000Z';new_date='2026-11-09T12:00:00.000Z'
    results=[]
    def check(name,action):
        t=time.perf_counter();detail=action()
        results.append({'case':name,'passed':True,'milliseconds':round((time.perf_counter()-t)*1000,3),'detail':detail})
    def rejected(action,expected):
        try:action()
        except expected as error:return type(error).__name__
        raise AssertionError('Modified archive unexpectedly accepted')
    for password in ('A','cat','☕ spaces, punctuation!'):
        t=time.perf_counter();blob=seal(raw,password,created)
        seal_ms=(time.perf_counter()-t)*1000
        def round_trip():
            restored=unlock(blob,password)
            assert restored==raw;validate_chain(restored)
            return {'password_fixture':password,'source_bytes':len(raw),'encrypted_bytes':len(blob),
                    'seal_ms':round(seal_ms,3),'sha256':hashlib.sha256(restored).hexdigest()}
        check('exact_round_trip_'+password,round_trip)
    blob=seal(raw,'cat',created)
    check('edited_date_rejected',lambda:rejected(lambda:unlock(change_header(blob,original_created_at=new_date),'cat'),InvalidTag))
    check('date_cleared_rejected',lambda:rejected(lambda:unlock(change_header(blob,original_created_at=None),'cat'),ValueError))
    def remove_date():
        header,_,ciphertext,signature,_,_=parts(blob)
        del header['original_created_at']
        return rejected(lambda:unlock(envelope(header,ciphertext,signature),'cat'),ValueError)
    check('date_field_removed_rejected',remove_date)
    check('wrong_password_rejected',lambda:rejected(lambda:unlock(blob,'wrong'),InvalidTag))
    corrupt=bytearray(blob);corrupt[-17]^=1
    check('corrupted_ciphertext_rejected',lambda:rejected(lambda:unlock(bytes(corrupt),'cat'),InvalidTag))
    check('truncated_file_rejected',lambda:rejected(lambda:unlock(blob[:-1],'cat'),InvalidTag))
    out.mkdir(parents=True,exist_ok=True)
    path=out/'synthetic-copy.date-test';path.write_bytes(blob)
    copied=out/'renamed-copy.date-test';copied.write_bytes(path.read_bytes());os.utime(copied,(1,1))
    def copied_file():
        assert unlock(copied.read_bytes(),'cat')==raw
        assert parts(copied.read_bytes())[0]['original_created_at']==created
        return 'Copy, rename and filesystem timestamp change preserve the embedded original'
    check('filesystem_date_not_authoritative',copied_file)
    def key_binding():
        salt=b'0123456789abcdef'
        assert derive('cat',created,salt)!=derive('cat',new_date,salt)
        return 'Same password/salt, different dates: different keys'
    check('date_changes_derived_key',key_binding)
    def owner_rewrap():
        replacement=seal(unlock(blob,'cat'),'cat',new_date)
        assert unlock(replacement,'cat')==raw
        assert parts(replacement)[0]['original_created_at']==new_date
        return 'Password holder can produce a valid replacement with a new asserted date'
    check('password_holder_can_reencrypt_with_new_date',owner_rewrap)
    signer=Ed25519PrivateKey.generate();trusted=signer.public_key()
    signed=seal(raw,'cat',created,signer)
    check('date_verified_without_password',lambda:verify_signature(signed,trusted)['original_created_at'])
    check('edited_signed_date_rejected',lambda:rejected(lambda:verify_signature(
        change_header(signed,original_created_at=new_date),trusted),InvalidSignature))
    def wrong_signer():
        forged=seal(raw,'cat',new_date,Ed25519PrivateKey.generate())
        return rejected(lambda:unlock(forged,'cat',trusted,True),InvalidSignature)
    check('password_holder_without_signing_key_rejected',wrong_signer)
    check('signature_downgrade_rejected',lambda:rejected(lambda:unlock(blob,'cat',trusted,True),ValueError))
    def false_clock():
        asserted='2001-01-01T00:00:00.000Z'
        backdated=seal(raw,'cat',asserted,signer)
        assert verify_signature(backdated,trusted)['original_created_at']==asserted
        return 'Valid signature authenticates an assertion; it does not establish real wall-clock creation'
    check('incorrect_clock_can_be_signed',false_clock)
    report={'schema':'blackbox-date-binding-study/1','cryptography':cryptography.__version__,
        'zstandard':zstandard.__version__,'kdf':PARAMS,'cipher':'AES-256-GCM, 96-bit random nonce, full header AAD',
        'signature':'Ed25519; trusted public key supplied externally; private key only in test memory',
        'scope':'Isolated generated data. No production encryption or retention policy configured.',
        'cases':results}
    (out/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    study(parser.parse_args().out)
