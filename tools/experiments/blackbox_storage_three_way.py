"""Offline compression experiment. Not imported by the recording runtime.

Three families: gzip; byte-preserving Zstd (with/without a trained dictionary);
reversible columnar MessagePack + Zstd. No source deletion or live-log changes.
Test dependencies: zstandard, msgpack. Both are optional outside this tool.
"""
from __future__ import annotations
import argparse
import asyncio
import base64
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import random
try:
    import resource
except ImportError:  # Windows can run codecs; Linux-specific RSS is unavailable.
    resource=None
import statistics
import struct
import subprocess
import sys
import time
import threading

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from blackbox_event_language.schema import (
    BLACKBOX_KEY, REQUIRED_FIELDS, BlackBoxRecord, ZERO_HASH, encode_record, parse_record)
from blackbox_recorder import map_pubcast_event

MAGIC=b'BBXTEST1'
METHODS=('gzip6','zstd3','zstd9','zstd9_dict','column9')


def digest(data):return hashlib.sha256(data).hexdigest()


def memory_mib():
    # The sandbox PID namespace differs from /proc numeric PIDs. /proc/self
    # identifies this process correctly; psutil.Process(getpid()) did not.
    values={}
    if not Path('/proc/self/status').is_file():return None,None
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith(('VmRSS:','VmHWM:')):
            key,value,*_=line.split();values[key[:-1]]=int(value)/1024
    return values['VmRSS'],values['VmHWM']


def chunks(raw, target):
    current=bytearray()
    for line in raw.splitlines(keepends=True):
        if current and len(current)+len(line)>target:
            yield bytes(current);current.clear()
        current.extend(line)
    if current:yield bytes(current)


def pack_columns(raw):
    import msgpack
    rows=[];previous=None
    for line in raw.decode('utf-8').splitlines(keepends=True):
        fields=parse_record(line)
        canonical='BBX1|'+'|'.join(f'{key}={fields[key]}' for key in REQUIRED_FIELDS)+'\n'
        if canonical!=line or (previous is not None and fields['ph']!=previous):
            # Preserve unusual historical formatting without reinterpretation.
            return msgpack.packb([0,raw],use_bin_type=True)
        rows.append(fields);previous=fields['h']
    columns=[]
    for key in REQUIRED_FIELDS:
        if key=='ph':continue
        values=[bytes.fromhex(r[key]) if key=='h' else r[key] for r in rows]
        columns.append([0,values[0]] if all(v==values[0] for v in values) else [1,values])
    return msgpack.packb([1,bytes.fromhex(rows[0]['ph']),len(rows),columns],use_bin_type=True)


def unpack_columns(packed):
    import msgpack
    data=msgpack.unpackb(packed,raw=False)
    if data[0]==0:return data[1]
    _,previous,count,columns=data
    result=[]
    for i in range(count):
        fields={'ph':previous.hex()}
        for key,column in zip((k for k in REQUIRED_FIELDS if k!='ph'),columns):
            value=column[1] if column[0]==0 else column[1][i]
            fields[key]=value.hex() if key=='h' else value
        result.append('BBX1|'+'|'.join(f'{key}={fields[key]}' for key in REQUIRED_FIELDS)+'\n')
        previous=bytes.fromhex(fields['h'])
    return ''.join(result).encode('utf-8')


def contexts(method,dictionary):
    if method=='gzip6':return None,None
    import zstandard as zstd
    dd=zstd.ZstdCompressionDict(dictionary) if method=='zstd9_dict' else None
    return (zstd.ZstdCompressor(level=3 if method=='zstd3' else 9,dict_data=dd,write_checksum=True),
            zstd.ZstdDecompressor(dict_data=dd,max_window_size=16384))


def encode(raw,method,target,dictionary=b''):
    compressor,_=contexts(method,dictionary)
    frames=[];index=[];offset=0
    for block in chunks(raw,target):
        packed=pack_columns(block) if method=='column9' else block
        frame=gzip.compress(packed,compresslevel=6,mtime=0) if method=='gzip6' else compressor.compress(packed)
        index.append({'offset':offset,'size':len(frame),'raw_size':len(block),
                      'packed_size':len(packed),'sha256':digest(block)})
        offset+=len(frame);frames.append(frame)
    dd=dictionary if method=='zstd9_dict' else b''
    header={'schema':'blackbox-compression-experiment/1','method':method,'raw_size':len(raw),
            'sha256':digest(raw),'frames':index,'key':BLACKBOX_KEY,
            'dictionary':base64.b64encode(dd).decode('ascii'),'dictionary_sha256':digest(dd)}
    wire=json.dumps(header,ensure_ascii=False,separators=(',', ':')).encode()
    return MAGIC+struct.pack('>I',len(wire))+wire+b''.join(frames)


def header_of(archive):
    if archive[:8]!=MAGIC:raise ValueError('Bad experiment archive magic')
    length=struct.unpack('>I',archive[8:12])[0]
    if len(archive)<12+length:raise ValueError('Incomplete archive header')
    return json.loads(archive[12:12+length]),12+length


def decode_frame(archive,index):
    header,start=header_of(archive);entry=header['frames'][index]
    dd=base64.b64decode(header['dictionary'])
    if digest(dd)!=header['dictionary_sha256']:raise ValueError('Dictionary checksum mismatch')
    _,decompressor=contexts(header['method'],dd)
    frame=archive[start+entry['offset']:start+entry['offset']+entry['size']]
    if len(frame)!=entry['size']:raise ValueError('Incomplete frame')
    packed=gzip.decompress(frame) if header['method']=='gzip6' else decompressor.decompress(
        frame,max_output_size=entry['packed_size'],allow_extra_data=False)
    raw=unpack_columns(packed) if header['method']=='column9' else packed
    if len(raw)!=entry['raw_size'] or digest(raw)!=entry['sha256']:raise ValueError('Frame checksum mismatch')
    return raw


def decode(archive):
    header,_=header_of(archive)
    raw=b''.join(decode_frame(archive,i) for i in range(len(header['frames'])))
    if len(raw)!=header['raw_size'] or digest(raw)!=header['sha256']:raise ValueError('Archive checksum mismatch')
    return raw


def validate_chain(raw):
    previous=ZERO_HASH
    for seq,line in enumerate(raw.decode().splitlines()):
        record=parse_record(line)
        if int(record['seq'])!=seq or record['ph']!=previous:raise ValueError('Broken reconstructed chain')
        previous=record['h']


def workload(count,seed,entropy=False):
    rng=random.Random(seed);previous=ZERO_HASH;result=[]
    phrases=['Check the camera, then wait for the cue.','A different idea: let the guest finish first.',
             'The system should preserve this exact text.','Here is an observation about the next take.',
             'Coffee, continuity, lighting — keep the original. ☕','Why did the previous request stop?']
    for n in range(count):
        nonce=rng.randbytes(16).hex()
        if entropy:
            kind='system.event';data={'blob':base64.b64encode(rng.randbytes(768)).decode(),
                'request_id':nonce,'state':'received','sequence':n}
        elif n%5==0:
            kind='system.event';data={'event':{'type':'production_state','payload':{
                'scene':f'set-{n%7}','ready':bool(n%2),'camera':f'cam-{n%4}',
                'levels':{'dialogue':.73,'music':.2},'request_id':nonce}}}
        elif n%5==1:
            kind='partner.generation';data={'generation_id':nonce,'bot_id':f'bot-{n%9}',
                'room':'studio','state':'completed','offline':True,'message_id':rng.randbytes(16).hex()}
        else:
            kind='chat.message';data={'text':rng.choice(phrases)+' '+rng.choice(phrases)+f' Take {n}.',
                'room':f'room-{n%11}','t':1800000000+n*.053,'message_id':nonce}
        mapped=map_pubcast_event({'event_type':kind,'source':'system' if entropy else 'chat',
                                  'actor':f'user-{n%19}','data':data})
        timestamp=(datetime(2026,11,9,tzinfo=timezone.utc)+timedelta(milliseconds=n*53)).isoformat(timespec='milliseconds').replace('+00:00','Z')
        record=BlackBoxRecord(seq=n,ch=mapped.ch,src=mapped.src,act=mapped.act,ev=mapped.ev,cov=mapped.cov,
            sid=f'fixture_{seed}',rid=f'fixture_{seed}:{n}',ph=previous,t=timestamp,payload=mapped.payload)
        wire=encode_record(record);previous=parse_record(wire)['h'];result.append(wire+'\n')
    return ''.join(result).encode()


async def runtime_trace(root):
    from modules.blackbox_runtime import create_blackbox_witness
    from modules.hub import Hub
    from modules.bots import BotManager
    from modules.models import BotConfig,BotProvider
    hub=Hub(root);w=create_blackbox_witness(root,session_id='runtime_generated');hub.blackbox_witness=w
    for n in range(48):
        await hub.post_chat_message('studio',f'fixture-user-{n%5}',f'Generated runtime message {n}, exact.\n☕')
        if n%3==0:await hub.broadcast_system_event({'type':'production_state','payload':{'take':n,'ready':True}})
    bots=BotManager(root,hub)
    bots.upsert_config(BotConfig(bot_id='fixture',name='Fixture',provider=BotProvider.OLLAMA,
        model='fixture',api_key_env='',rooms=['studio']))
    async def generated_reply(*args):return 'Generated bot reply, through real storage and event paths.'
    bots._call_provider=generated_reply
    for _ in range(8):await bots.request_turn('fixture','studio','Consider this fixture.',actor='system:jeremy',required=True)
    w.close();return w.path.read_bytes()


def worker(args):
    import zstandard,msgpack
    raw=args.corpus.read_bytes();dictionary=args.dictionary.read_bytes()
    before,_=memory_mib()
    peak=[before];stop=threading.Event()
    def sample_memory():
        while not stop.wait(.001):
            current=memory_mib()[0]
            if current is not None:peak[0]=max(peak[0],current)
    sampler=threading.Thread(target=sample_memory,daemon=True);sampler.start()
    enc=[];dec=[]
    for _ in range(args.repeats):
        t=time.perf_counter();archive=encode(raw,args.method,args.target,dictionary);enc.append(time.perf_counter()-t)
        t=time.perf_counter();restored=decode(archive);dec.append(time.perf_counter()-t)
        if restored!=raw:raise AssertionError('Non-identical source bytes')
    validate_chain(restored)
    header,start=header_of(archive)
    middle=len(header['frames'])//2
    t=time.perf_counter();decode_frame(archive,middle);seek_ms=(time.perf_counter()-t)*1000
    damaged=bytearray(archive);entry=header['frames'][middle]
    damaged[start+entry['offset']+entry['size']//2]^=1
    recovered=0;bad=0
    for i in range(len(header['frames'])):
        try:decode_frame(bytes(damaged),i);recovered+=1
        except Exception:bad+=1
    if bad!=1:raise AssertionError('Corruption not isolated to one frame')
    truncated=archive[:-max(1,header['frames'][-1]['size']//2)]
    prefix=0
    for i in range(len(header['frames'])):
        try:decode_frame(truncated,i);prefix+=1
        except Exception:break
    if prefix!=len(header['frames'])-1:raise AssertionError('Unexpected truncation recovery')
    args.archive.write_bytes(archive)
    current,high_water=memory_mib()
    if current is not None:peak[0]=max(peak[0],current,high_water)
    stop.set();sampler.join()
    result={'corpus':args.corpus.stem,'method':args.method,'target':args.target,'raw_bytes':len(raw),
        'archive_bytes':len(archive),'header_bytes':start,'frames':len(header['frames']),
        'saved_percent':round(100*(1-len(archive)/len(raw)),3),
        'encode_ms':round(statistics.median(enc)*1000,3),'decode_ms':round(statistics.median(dec)*1000,3),
        'middle_frame_ms':round(seek_ms,3),'peak_rss_mib':round(peak[0],2) if peak[0] is not None else None,
        'kernel_high_water_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2) if resource else None,
        'loaded_rss_mib':round(before,2) if before is not None else None,'exact_bytes':True,'chain_valid':True,
        'corruption_bad_frames':bad,'intact_frames_recovered':recovered,'truncated_frames_recovered':prefix,
        'sha256':digest(raw),'archive_sha256':digest(archive),'zstd':zstandard.__version__,'msgpack':msgpack.__version__}
    print(json.dumps(result))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path);p.add_argument('--worker',action='store_true')
    p.add_argument('--corpus',type=Path);p.add_argument('--dictionary',type=Path)
    p.add_argument('--method',choices=METHODS);p.add_argument('--target',type=int)
    p.add_argument('--archive',type=Path);p.add_argument('--repeats',type=int,default=3)
    args=p.parse_args()
    if args.worker:worker(args);return
    import zstandard,msgpack
    args.out.mkdir(parents=True,exist_ok=True)
    corpora={'mixed':workload(4096,7),'entropy':workload(1024,19,True),'tiny':workload(32,29),
             'runtime':asyncio.run(runtime_trace(args.out/'isolated-runtime'))}
    samples=workload(2000,99).splitlines(keepends=True)
    t=time.perf_counter();dictionary=zstandard.train_dictionary(8192,samples).as_bytes()
    training_ms=(time.perf_counter()-t)*1000
    dictionary_path=args.out/'training.dict';dictionary_path.write_bytes(dictionary)
    rows=[]
    for name,raw in corpora.items():
        validate_chain(raw);path=args.out/(name+'.bbx');path.write_bytes(raw)
        for target in (16384,65536,262144,8388608):
            for method in METHODS:
                archive=args.out/f'{name}-{target}-{method}.bbxtest'
                command=[sys.executable,str(Path(__file__).resolve()),'--worker','--corpus',str(path),
                    '--dictionary',str(dictionary_path),'--method',method,'--target',str(target),'--archive',str(archive),
                    '--repeats',str(args.repeats)]
                completed=subprocess.run(command,capture_output=True,text=True,timeout=90)
                if completed.returncode:raise RuntimeError(completed.stderr[-4000:])
                row=json.loads(completed.stdout);rows.append(row)
                print(f"{name} {target} {method}: {row['saved_percent']}% saved, {row['encode_ms']}ms",flush=True)
    report={'schema':'blackbox-three-way-results/1','platform':platform.platform(),'python':sys.version,
        'zstandard':zstandard.__version__,'zstd_engine':zstandard.ZSTD_VERSION,'msgpack':msgpack.__version__,
        'repeats':args.repeats,'dictionary_bytes':len(dictionary),'dictionary_training_ms':training_ms,
        'dictionary_training':'disjoint generated mixed workload seed 99; test seeds 7,19,29 and real generated runtime',
        'memory_note':'Linux /proc/self VmHWM and 1ms VmRSS samples per fresh exec; includes Python, libraries, full input/output and damage tests. getrusage recorded separately because it inherited a pre-exec floor. Numeric-PID psutil sampling was invalid in this sandbox and discarded.',
        'timing_note':'Median in-process encode/decode times; excludes filesystem fsync, process startup and training; full decode includes per-frame context/header work',
        'rows':rows}
    (args.out/'results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
