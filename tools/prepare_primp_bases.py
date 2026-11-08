"""Build paint-ready derivatives; never alter the source Manny/Sheila GLBs.

Build dependencies: numpy, Pillow, xatlas==0.0.11 (MIT). Not used at app startup.
"""
from __future__ import annotations
import copy
import hashlib
import io
import json
from pathlib import Path
import struct
import numpy as np
from PIL import Image, ImageFilter
import xatlas

ROOT = Path(__file__).resolve().parents[1]
DTYPE = {5121: np.dtype('u1'), 5123: np.dtype('<u2'), 5125: np.dtype('<u4'), 5126: np.dtype('<f4')}
WIDTH = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def read_glb(path):
    raw = path.read_bytes()
    length = struct.unpack_from('<I', raw, 12)[0]
    document = json.loads(raw[20:20 + length])
    offset = 20 + length
    assert struct.unpack_from('<I', raw, offset + 4)[0] == 0x004e4942
    binary = bytearray(raw[offset + 8:offset + 8 + document['buffers'][0]['byteLength']])
    return raw, document, binary


def values(document, binary, accessor_id):
    accessor = document['accessors'][accessor_id]
    view = document['bufferViews'][accessor['bufferView']]
    if accessor.get('sparse') or view.get('byteStride'):
        raise ValueError('This derivative builder requires the original packed base assets.')
    offset = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
    return np.frombuffer(binary, dtype=DTYPE[accessor['componentType']], count=accessor['count'] * WIDTH[accessor['type']], offset=offset).reshape(-1, WIDTH[accessor['type']]).copy()


def append_view(document, binary, data, target=None):
    binary.extend(b'\0' * (-len(binary) % 4))
    view = {'buffer': 0, 'byteOffset': len(binary), 'byteLength': len(data)}
    if target is not None:
        view['target'] = target
    binary.extend(data)
    document['bufferViews'].append(view)
    return len(document['bufferViews']) - 1


def append_accessor(document, binary, data, template, target=None):
    accessor = copy.deepcopy(template)
    accessor.pop('byteOffset', None)
    accessor.pop('min', None)
    accessor.pop('max', None)
    accessor['bufferView'] = append_view(document, binary, data.tobytes(), target)
    accessor['count'] = len(data)
    if accessor['type'].startswith('VEC') and data.dtype.kind == 'f':
        accessor['min'] = data.min(axis=0).tolist()
        accessor['max'] = data.max(axis=0).tolist()
    document['accessors'].append(accessor)
    return len(document['accessors']) - 1


def bake_colors(uv, triangles, colors, resolution=2048):
    pixels = np.zeros((resolution, resolution, 4), dtype=np.uint8)
    covered = np.zeros((resolution, resolution), dtype=bool)
    for tri in triangles:
        p = uv[tri].astype(np.float64) * resolution
        x0, y0 = np.maximum(0, np.floor(p.min(axis=0)).astype(int))
        x1, y1 = np.minimum(resolution - 1, np.ceil(p.max(axis=0)).astype(int))
        if x1 < x0 or y1 < y0:
            continue
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        xx, yy = xx + .5, yy + .5
        denominator = (p[1,1]-p[2,1])*(p[0,0]-p[2,0])+(p[2,0]-p[1,0])*(p[0,1]-p[2,1])
        if abs(denominator) < 1e-12:
            continue
        a = ((p[1,1]-p[2,1])*(xx-p[2,0])+(p[2,0]-p[1,0])*(yy-p[2,1])) / denominator
        b = ((p[2,1]-p[0,1])*(xx-p[2,0])+(p[0,0]-p[2,0])*(yy-p[2,1])) / denominator
        c = 1-a-b
        mask = (a >= -1e-8) & (b >= -1e-8) & (c >= -1e-8)
        rgba = a[...,None]*colors[tri[0]] + b[...,None]*colors[tri[1]] + c[...,None]*colors[tri[2]]
        rgb = np.clip(rgba[...,:3], 0, 1)
        rgba[...,:3] = np.where(rgb <= .0031308, rgb*12.92, 1.055*np.power(rgb, 1/2.4)-.055)
        pixels[y0:y1+1,x0:x1+1][mask] = np.rint(np.clip(rgba[mask], 0, 1)*255).astype(np.uint8)
        covered[y0:y1+1,x0:x1+1] |= mask
    # Extrude base colors into padding; never alter covered source colors.
    expanded = np.asarray(Image.fromarray(pixels).filter(ImageFilter.MaxFilter(9)))
    pixels[~covered] = expanded[~covered]
    output = io.BytesIO()
    Image.fromarray(pixels).save(output, format='PNG', optimize=True)
    return output.getvalue()


def prepare(name):
    source = ROOT / 'assets' / 'avatar' / f'{name}.glb'
    raw, original, binary = read_glb(source)
    document = copy.deepcopy(original)
    if len(document['buffers']) != 1:
        raise ValueError('Expected one embedded buffer in the legacy base.')
    for view in document['bufferViews']:
        view.setdefault('buffer', 0)
    primitive = document['meshes'][0]['primitives'][0]
    original_attributes = primitive['attributes'].copy()
    position = values(document, binary, original_attributes['POSITION'])
    triangles = values(document, binary, primitive['indices']).reshape(-1, 3).astype(np.uint32)
    atlas = xatlas.Atlas()
    atlas.add_mesh(position.astype(np.float32), triangles)
    options = xatlas.PackOptions()
    options.resolution = 2048
    options.padding = 8
    options.bilinear = True
    atlas.generate(pack_options=options)
    if atlas.atlas_count != 1:
        raise ValueError('Expected one texture atlas.')
    mapping, indices, uv = atlas[0]
    if not np.array_equal(mapping[indices], triangles):
        raise ValueError('UV unwrapping changed triangle order or winding.')
    for semantic, accessor_id in original_attributes.items():
        if semantic == 'COLOR_0':
            continue
        remapped = values(document, binary, accessor_id)[mapping]
        primitive['attributes'][semantic] = append_accessor(document, binary, remapped, document['accessors'][accessor_id], 34962)
    primitive['attributes'].pop('COLOR_0', None)
    primitive['attributes']['TEXCOORD_0'] = append_accessor(document, binary, uv.astype('<f4'), {'componentType':5126,'type':'VEC2'}, 34962)
    primitive['indices'] = append_accessor(document, binary, indices.reshape(-1,1).astype('<u4'), {'componentType':5125,'type':'SCALAR'}, 34963)
    colors = values(document, binary, original_attributes['COLOR_0'])[mapping]
    image = bake_colors(uv, indices, colors)
    document.setdefault('images', []).append({'bufferView': append_view(document,binary,image), 'mimeType':'image/png'})
    document.setdefault('samplers', []).append({'magFilter':9729,'minFilter':9987,'wrapS':33071,'wrapT':33071})
    document.setdefault('textures', []).append({'source':len(document['images'])-1,'sampler':len(document['samplers'])-1})
    document['materials'][primitive['material']]['pbrMetallicRoughness']['baseColorTexture'] = {'index':len(document['textures'])-1}
    source_hash = hashlib.sha256(raw).hexdigest()
    document.setdefault('extras', {})['primpPreparation'] = {'source':f'assets/avatar/{name}.glb','sha256':source_hash,'unwrap':'xatlas 0.0.11','resolution':2048,'padding':8,'vertexColors':'baked into sRGB texture; original material and emission retained'}
    document['buffers'][0]['byteLength'] = len(binary)
    text = json.dumps(document, separators=(',',':'), ensure_ascii=False).encode()
    text += b' ' * (-len(text)%4)
    binary.extend(b'\0' * (-len(binary)%4))
    result = struct.pack('<III',0x46546c67,2,12+8+len(text)+8+len(binary))+struct.pack('<II',len(text),0x4e4f534a)+text+struct.pack('<II',len(binary),0x004e4942)+binary
    destination = ROOT/'static'/'primp'/'avatars'/f'{name}.glb'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(result)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    return {'name':name,'source_sha256':source_hash,'derived_sha256':hashlib.sha256(result).hexdigest(),'vertices':len(mapping),'triangles':len(indices),'charts':atlas.chart_count,'bytes':len(result)}


if __name__ == '__main__':
    records = [prepare(name) for name in ('manny','sheila')]
    (ROOT/'static'/'primp'/'avatars'/'PROVENANCE.json').write_text(json.dumps({'tool':'xatlas 0.0.11','tool_license':'MIT','tool_source':'https://github.com/mworchel/xatlas-python/tree/v0.0.11','records':records},indent=2)+'\n')
    print(json.dumps(records,indent=2))
