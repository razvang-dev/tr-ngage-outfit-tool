#!/usr/bin/env python3
"""Minimal Tomb Editor WAD2 reader used by TR N-Gage Outfit Tool.

Supported portions are intentionally narrow: embedded textures, moveables, meshes,
polygon UVs, and Bone2 metadata needed for Lara skin conversion/export.
"""
from __future__ import annotations
from pathlib import Path
import struct

class WAD2Error(RuntimeError):
    pass

def read_sleb(data: bytes, pos: int):
    result=0; shift=0
    while True:
        if pos>=len(data): raise WAD2Error('Unexpected EOF while reading WAD2 SLEB128')
        b=data[pos]; pos+=1
        result |= (b & 0x7f) << shift
        shift += 7
        if (b & 0x80)==0: break
        if shift>63: raise WAD2Error('WAD2 SLEB128 value is too large')
    if shift<64 and (b & 0x40): result |= -(1 << shift)
    return result,pos

def read_chunk_id(data: bytes, pos: int):
    n,pos=read_sleb(data,pos)
    if n==0: return '',pos
    if n<0 or pos+n>len(data): raise WAD2Error(f'Invalid WAD2 chunk-id length {n}')
    return data[pos:pos+n].decode('utf-8','replace'),pos+n

def parse_chunks(data: bytes, start: int, end: int):
    out=[]; pos=start
    while pos<end:
        cid,p=read_chunk_id(data,pos)
        if cid=='': return out,p
        size,p=read_sleb(data,p)
        if size<0 or p+size>end: raise WAD2Error(f'Chunk {cid!r} at 0x{pos:X} has invalid size {size}')
        out.append((cid,p,p+size,size)); pos=p+size
    return out,pos

def parse_textures(data,start,end):
    textures=[]; auto=0
    for cid,s,e,_ in parse_chunks(data,start,end)[0]:
        if cid!='W2Txt': continue
        p=s; width,p=read_sleb(data,p); height,p=read_sleb(data,p)
        rec={'index':auto,'width':width,'height':height,'name':'','relative_path':'','data':b''}
        for sid,ss,se,_ in parse_chunks(data,p,e)[0]:
            if sid=='W2Index': rec['index'],_=read_sleb(data,ss)
            elif sid=='W2TxtName': rec['name']=data[ss:se].decode('utf-8','replace')
            elif sid=='W2TxtRelPath': rec['relative_path']=data[ss:se].decode('utf-8','replace')
            elif sid=='W2TxtData': rec['data']=data[ss:se]
        auto=rec['index']+1
        if rec['width']<=0 or rec['height']<=0: raise WAD2Error(f'Texture {rec["index"]} has invalid size')
        expected=rec['width']*rec['height']*4
        if len(rec['data'])!=expected:
            raise WAD2Error(f'Texture {rec["index"]}: expected {expected} BGRA bytes, got {len(rec["data"])}')
        textures.append(rec)
    return textures

def parse_mesh(data,start,end):
    mesh={'name':'','positions':[],'normals':[],'polygons':[],'sphere_center':None,'sphere_radius':None,'bbox_min':None,'bbox_max':None}
    for cid,s,e,_ in parse_chunks(data,start,end)[0]:
        if cid=='W2MeshName': mesh['name']=data[s:e].decode('utf-8','replace')
        elif cid=='W2MeshSphere':
            for sid,ss,se,_ in parse_chunks(data,s,e)[0]:
                if sid=='W2SphC' and se-ss>=12: mesh['sphere_center']=struct.unpack_from('<fff',data,ss)
                elif sid=='W2SphR' and se-ss>=8: mesh['sphere_radius']=struct.unpack_from('<d',data,ss)[0]
        elif cid=='W2BBox':
            for sid,ss,se,_ in parse_chunks(data,s,e)[0]:
                if sid=='W2BBMin' and se-ss>=12: mesh['bbox_min']=struct.unpack_from('<fff',data,ss)
                elif sid=='W2BBMax' and se-ss>=12: mesh['bbox_max']=struct.unpack_from('<fff',data,ss)
        elif cid=='W2VrtPos':
            for sid,ss,se,_ in parse_chunks(data,s,e)[0]:
                if sid=='W2Pos':
                    if se-ss<12: raise WAD2Error('W2Pos is truncated')
                    mesh['positions'].append(struct.unpack_from('<fff',data,ss))
        elif cid=='W2VrtNorm':
            for sid,ss,se,_ in parse_chunks(data,s,e)[0]:
                if sid=='W2N':
                    if se-ss<12: raise WAD2Error('W2N is truncated')
                    mesh['normals'].append(struct.unpack_from('<fff',data,ss))
        elif cid=='W2Polys':
            for sid,ss,se,_ in parse_chunks(data,s,e)[0]:
                if sid not in ('W2Uq','W2Uq2','W2Tr','W2Tr2'): continue
                p=ss; quad=sid in ('W2Uq','W2Uq2'); v2=sid in ('W2Uq2','W2Tr2'); n=4 if quad else 3
                indices=[]
                for _ in range(n): v,p=read_sleb(data,p); indices.append(v)
                shine,p=read_sleb(data,p); texture,p=read_sleb(data,p)
                parent=None
                if v2:
                    if p+16>se: raise WAD2Error(f'{sid} parent-area is truncated')
                    parent=struct.unpack_from('<ffff',data,p); p+=16
                uvs=[]
                for _ in range(n):
                    if p+8>se: raise WAD2Error(f'{sid} UV data is truncated')
                    uvs.append(struct.unpack_from('<ff',data,p)); p+=8
                blend,p=read_sleb(data,p)
                if p>=se: raise WAD2Error(f'{sid} double-sided flag is truncated')
                double_sided=bool(data[p]); p+=1
                mesh['polygons'].append({'shape':'quad' if quad else 'triangle','v':indices,'texture':texture,
                                         'uvs':uvs,'shine':shine,'blend':blend,'double_sided':double_sided,
                                         'parent':parent,'chunk':sid})
    return mesh

def parse_bone2(data,start,end):
    p=start; opcode,p=read_sleb(data,p)
    if p+4>end: raise WAD2Error('W2Bone2 name length is truncated')
    n=struct.unpack_from('<i',data,p)[0]; p+=4
    if n<0 or p+n>end: raise WAD2Error('W2Bone2 has invalid name length')
    name=data[p:p+n].decode('utf-8','replace'); p+=n
    bone={'opcode':opcode,'name':name,'mesh':None,'translation':None}
    for cid,s,e,_ in parse_chunks(data,p,end)[0]:
        if cid=='W2BoneMesh': bone['mesh'],_=read_sleb(data,s)
        elif cid=='W2BoneTrans':
            if e-s>=12: bone['translation']=struct.unpack_from('<fff',data,s)
    return bone

def parse_moveables(data,start,end):
    out=[]
    for cid,s,e,_ in parse_chunks(data,start,end)[0]:
        if cid!='W2Moveable': continue
        p=s; object_id,p=read_sleb(data,p)
        rec={'object_id':object_id,'meshes':[],'bones':[],'animation_chunks':0}
        for sid,ss,se,_ in parse_chunks(data,p,e)[0]:
            if sid=='W2Mesh': rec['meshes'].append(parse_mesh(data,ss,se))
            elif sid=='W2Bone2': rec['bones'].append(parse_bone2(data,ss,se))
            elif sid in ('W2Ani','W2Ani2','W2Ani3','W2Anm'): rec['animation_chunks']+=1
        out.append(rec)
    return out

def load(path: Path):
    data=Path(path).read_bytes()
    if len(data)<8 or data[:4]!=b'WAD2': raise WAD2Error('Not a WAD2 file')
    version=struct.unpack_from('<I',data,4)[0]
    if version!=0: raise WAD2Error(f'Unsupported WAD2 container version {version}; this tool currently supports version 0')
    result={'path':str(path),'data':data,'version':version,'suggested_game_version':None,'sound_system':None,
            'textures':[],'moveables':[]}
    for cid,s,e,_ in parse_chunks(data,8,len(data))[0]:
        if cid=='W2SuggestedGameVersion': result['suggested_game_version'],_=read_sleb(data,s)
        elif cid=='W2SoundSystem': result['sound_system'],_=read_sleb(data,s)
        elif cid=='W2Textures': result['textures']=parse_textures(data,s,e)
        elif cid=='W2Moveables': result['moveables']=parse_moveables(data,s,e)
    return result

def texture_by_index(wad,index):
    for t in wad['textures']:
        if t['index']==index: return t
    raise WAD2Error(f'WAD2 refers to missing texture index {index}')

def pixel_rgba(texture,x,y):
    x=max(0,min(texture['width']-1,int(x))); y=max(0,min(texture['height']-1,int(y)))
    o=(y*texture['width']+x)*4
    b,g,r,a=texture['data'][o:o+4]
    return (r,g,b,a)
