#!/usr/bin/env python3
"""
TR N-Gage Outfit Tool v0.4.1

Hardware-proven conversion path:
  classic Tomb Raider WAD (file id 129)
      + original N-Gage deldata/lara.mesh
      -> new_tpage.tpa + retexture.dat

No third-party Python modules are required.

This release supports the hardware-proven classic-WAD path, a WAD-independent
editable texture workspace, and a first WAD2/Tomb Editor Lara-skin pipeline.
Topology-compatible WAD2 LARA_SKIN objects can be converted directly; incompatible
WAD2 geometry can be analyzed/exported for the geometry-development path.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import zlib
from collections import Counter, defaultdict

import wad2_support as wad2

VERSION = "0.4.1"
PRIMARY_NAMES = [
    'pelvis','left_thigh','left_knee_calf','left_ankle_foot',
    'right_thigh','right_knee_calf','right_ankle_foot','torso',
    'right_shoulder_upper_arm','right_elbow_lower_arm','right_wrist_hand',
    'left_shoulder_upper_arm','left_elbow_lower_arm','left_wrist_hand','head'
]
EXTRA_MAP = [(0x01,0x0D),(0x01,0x0A),(0x01,0x01),(0x01,0x04),
             (0x03,0x0D),(0x03,0x0A),(0x04,0x0D),(0x04,0x0A),
             (0x02,0x0D),(0x02,0x0A),(0x02,0x07)]
TRANSPARENT_DEFAULT = (255, 0, 255)
TPAGE = 0x0013
A_BASE_Y = 497
B_BASE_Y = 433
VRAM_X = 192
MAX_DESCRIPTORS = 101
MAX_PALETTES = 15
PIXEL_REGION_MAX_Y = 176  # rows 177..191 and 241..255 hold embedded CLUT banks


class ToolError(RuntimeError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def u16(b, o): return struct.unpack_from('<H', b, o)[0]
def s16(b, o): return struct.unpack_from('<h', b, o)[0]
def u32(b, o): return struct.unpack_from('<I', b, o)[0]
def i32(b, o): return struct.unpack_from('<i', b, o)[0]


def canon(v):
    v = tuple(v); n = len(v)
    rots = [v[i:] + v[:i] for i in range(n)]
    rv = tuple(reversed(v))
    rots += [rv[i:] + rv[:i] for i in range(n)]
    return min(rots)


def signed16(v):
    return struct.unpack('<h', struct.pack('<H', v))[0]


# ---------- N-Gage lara.mesh ----------
def parse_ngage_mesh_blob(blob: bytes, index: int, file_offset: int, words: int):
    if len(blob) < 14:
        raise ToolError(f"lara.mesh record {index} is too short")
    cx, cy, cz = s16(blob,0), s16(blob,2), s16(blob,4)
    radius = i32(blob,6)
    vc = s16(blob,10)
    n = abs(vc)
    p = 12
    positions = [struct.unpack_from('<4h', blob, p+i*8) for i in range(n)]
    p += n*8
    normals=[]; lights=[]
    if vc >= 0:
        normals = [struct.unpack_from('<4h', blob, p+i*8) for i in range(n)]
        p += n*8
    else:
        lights = [s16(blob,p+i*2) for i in range(n)]
        p += n*2
    qcount = u16(blob,p); p += 2
    quads=[]
    for _ in range(qcount):
        v = struct.unpack_from('<4H', blob, p)
        tex = u16(blob,p+8)
        quads.append({'v':list(v),'tex':tex}); p += 10
    tcount = u16(blob,p); p += 2
    tris=[]
    for _ in range(tcount):
        v = struct.unpack_from('<3H', blob, p)
        tex = u16(blob,p+6)
        tris.append({'v':list(v),'tex':tex}); p += 8
    if p != len(blob):
        raise ToolError(f"lara.mesh record {index}: parsed {p} bytes, blob has {len(blob)}")
    name = PRIMARY_NAMES[index] if index < 15 else f'extra_{EXTRA_MAP[index-15][0]:02X}_{EXTRA_MAP[index-15][1]:02X}'
    return {
        'index':index,'name':name,'file_offset':file_offset,'word_count':words,
        'center':[cx,cy,cz],'radius':radius,'vertex_count':vc,
        'positions':positions,'normals':normals,'lights':lights,
        'quads':quads,'triangles':tris
    }


def parse_ngage_lara(path: Path):
    data = path.read_bytes(); off=0; out=[]
    while off < len(data):
        if off+4 > len(data): raise ToolError('lara.mesh: truncated word count')
        words = u32(data,off); start=off+4; end=start+words*2
        if end > len(data): raise ToolError(f'lara.mesh record {len(out)} overruns file')
        out.append(parse_ngage_mesh_blob(data[start:end],len(out),off,words)); off=end
    if off != len(data): raise ToolError('lara.mesh did not reach exact EOF')
    if len(out) != 26:
        raise ToolError(f'Expected the known N-Gage lara.mesh layout of 26 records, got {len(out)}')
    return out


# ---------- Classic WAD ----------
def parse_classic_wad(path: Path):
    b = path.read_bytes()
    if len(b) < 16:
        raise ToolError('WAD file is too small')
    file_id = u32(b,0)
    if file_id != 129:
        raise ToolError(f'Unsupported WAD file id {file_id}. classic-WAD mode supports WAD id 129 only. Use the separate WAD2 Lab for .wad2 files.')
    num_samples = u32(b,4)
    sample_base = 8
    if sample_base + num_samples*8 + 4 > len(b):
        raise ToolError('WAD texture sample table is truncated')
    samples=[]
    for i in range(num_samples):
        x,y,page,flipx,addw,flipy,addh = struct.unpack_from('<BBHbBbB', b, sample_base+i*8)
        samples.append({'index':i,'x':x,'y':y,'page':page,'flipx':flipx,'flipy':flipy,
                        'w':addw+1,'h':addh+1,'addw':addw,'addh':addh})
    p = sample_base + num_samples*8
    tex_bytes = u32(b,p); p += 4
    if p + tex_bytes > len(b): raise ToolError('WAD RGB texture page block is truncated')
    tex_raw = b[p:p+tex_bytes]; p += tex_bytes
    page_bytes = 256*256*3
    if tex_bytes % page_bytes:
        raise ToolError(f'Expected RGB24 256x256 texture pages; texture byte count {tex_bytes} is not divisible by {page_bytes}')
    page_count = tex_bytes // page_bytes
    pages = [memoryview(tex_raw)[i*page_bytes:(i+1)*page_bytes] for i in range(page_count)]
    num_ptrs = u32(b,p); p += 4
    if p + num_ptrs*4 + 4 > len(b): raise ToolError('WAD mesh pointer table is truncated')
    ptrs = list(struct.unpack_from('<%dI' % num_ptrs, b, p)); p += 4*num_ptrs
    mesh_words = u32(b,p); p += 4
    mesh_base = p
    mesh_end = mesh_base + mesh_words*2
    if mesh_end > len(b): raise ToolError('WAD mesh block is truncated')
    return {
        'data':b,'path':str(path),'file_id':file_id,'samples':samples,'pages':pages,
        'texture_page_count':page_count,'texture_bytes':tex_bytes,
        'ptrs':ptrs,'mesh_base':mesh_base,'mesh_end':mesh_end,'mesh_words':mesh_words
    }


def parse_classic_mesh(wad, ptr_index: int):
    b=wad['data']; ptrs=wad['ptrs']; base=wad['mesh_base']; mend=wad['mesh_end']
    if not (0 <= ptr_index < len(ptrs)):
        raise ToolError(f'Bad mesh pointer index {ptr_index}')
    s = base + ptrs[ptr_index]
    if s < base or s+12 > mend:
        raise ToolError(f'Mesh pointer {ptr_index} points outside mesh block')
    cx,cy,cz,radius,unk,nv = struct.unpack_from('<hhhHHH', b, s)
    if nv > 4096: raise ToolError(f'Mesh {ptr_index}: unreasonable vertex count {nv}')
    q=s+12
    need=q+nv*6+2
    if need>mend: raise ToolError(f'Mesh {ptr_index}: vertex block truncated')
    verts=[struct.unpack_from('<hhh',b,q+i*6) for i in range(nv)]; q += nv*6
    nn=u16(b,q); q += 2
    if nn > 4096: raise ToolError(f'Mesh {ptr_index}: unreasonable normal count {nn}')
    if q+nn*6+2 > mend: raise ToolError(f'Mesh {ptr_index}: normal block truncated')
    normals=[struct.unpack_from('<hhh',b,q+i*6) for i in range(nn)]; q += nn*6
    npoly=u16(b,q); q += 2
    if npoly > 10000: raise ToolError(f'Mesh {ptr_index}: unreasonable polygon count {npoly}')
    faces=[]; quads=0
    for fi in range(npoly):
        if q+2>mend: raise ToolError(f'Mesh {ptr_index}: polygon {fi} truncated')
        shape=u16(b,q); q += 2
        if shape not in (8,9):
            raise ToolError(f'Mesh {ptr_index}: polygon {fi} has unsupported classic shape {shape}')
        nf=4 if shape==9 else 3
        if q+nf*2+4 > mend: raise ToolError(f'Mesh {ptr_index}: polygon {fi} data truncated')
        vs=list(struct.unpack_from('<'+'H'*nf,b,q)); q += nf*2
        tw=u16(b,q); q += 2
        attr=b[q]; unk8=b[q+1]; q += 2
        if nf==4: quads += 1
        faces.append({'v':vs,'texture_word':tw,'shape_record':shape,'attr':attr,'unk':unk8})
    if quads & 1:
        q += 2
        if q>mend: raise ToolError(f'Mesh {ptr_index}: padding runs past mesh block')
    return {'pointer_index':ptr_index,'center':[cx,cy,cz],'radius':radius,'unk':unk,
            'vertices':verts,'normals':normals,'faces':faces,'parsed_end':q}


def score_lara_candidate(wad, ng, start):
    if start+15 > len(wad['ptrs']): return None
    try:
        src=[parse_classic_mesh(wad,start+i) for i in range(15)]
    except Exception:
        return None
    vertex_exact=0; topology_match=0; topology_total=0
    for mi in range(15):
        if len(src[mi]['vertices']) == abs(ng[mi]['vertex_count']): vertex_exact += 1
        by=Counter((len(f['v']),canon(f['v'])) for f in src[mi]['faces'])
        for f in ng[mi]['quads']+ng[mi]['triangles']:
            topology_total += 1
            k=(len(f['v']),canon(f['v']))
            if by[k]:
                topology_match += 1
                by[k] -= 1
    # topology dominates; vertex count helps break ties.
    return {'start':start,'meshes':src,'vertex_count_matches':vertex_exact,
            'topology_matches':topology_match,'topology_total':topology_total,
            'score':topology_match*100 + vertex_exact}


def find_lara_skin(wad, ng, forced_start=None):
    if forced_start is not None:
        c=score_lara_candidate(wad,ng,forced_start)
        if c is None: raise ToolError(f'Could not parse 15 Lara meshes beginning at mesh pointer {forced_start}')
        return c
    candidates=[]
    for start in range(0,max(0,len(wad['ptrs'])-14)):
        c=score_lara_candidate(wad,ng,start)
        if c: candidates.append(c)
    if not candidates: raise ToolError('No parseable 15-mesh Lara candidate found in WAD')
    candidates.sort(key=lambda x:x['score'],reverse=True)
    best=candidates[0]
    coverage=best['topology_matches']/max(1,best['topology_total'])
    if best['vertex_count_matches'] < 13 or coverage < 0.70:
        raise ToolError('No sufficiently compatible TR1-style Lara skin was found. '
                        f'Best candidate starts at mesh pointer {best["start"]}, '
                        f'with {best["vertex_count_matches"]}/15 vertex-count matches and {coverage:.1%} topology coverage.')
    return best


def decode_classic_texture(face, samples):
    tw=face['texture_word']; nf=len(face['v'])
    if nf==4:
        if (tw & 0xF000)==0xF000:
            sample=-signed16(tw); extra_flip=True
        else:
            sample=tw & 0x0FFF; extra_flip=False
        tri_shape=None
    else:
        sample=tw & 0x0FFF
        tri_shape=(tw>>12)&0x7
        if tri_shape not in (0,2,4,6):
            raise ToolError(f'Unsupported classic triangle texture orientation {tri_shape}, word=0x{tw:04X}')
        extra_flip=bool(tw&0x8000)
    if not (0<=sample<len(samples)):
        raise ToolError(f'Texture word 0x{tw:04X} refers to missing sample {sample}')
    sm=samples[sample]
    x,y=sm['x'],sm['y']; aw,ah=sm['w']-1,sm['h']-1
    corners=[[x,y],[x+aw,y],[x+aw,y+ah],[x,y+ah]]
    if sm['flipx']==-1: corners=[corners[1],corners[0],corners[3],corners[2]]
    if sm['flipy']==-1: corners=[corners[3],corners[2],corners[1],corners[0]]
    if extra_flip: corners=[corners[1],corners[0],corners[3],corners[2]]
    if nf==4:
        uv=corners
    else:
        m={0:[3,0,1],2:[0,1,2],4:[1,2,3],6:[2,3,0]}
        uv=[corners[i] for i in m[tri_shape]]
    return sample, [(u-x,v-y) for u,v in uv]


# ---------- Raw RGB helpers ----------
def page_pixel(page, x, y):
    o=(y*256+x)*3
    return (page[o],page[o+1],page[o+2])


def crop_pixels(wad, si):
    sm=wad['samples'][si]
    if not (0 <= sm['page'] < len(wad['pages'])):
        raise ToolError(f'Sample {si} refers to texture page {sm["page"]}, but WAD has {len(wad["pages"])} pages')
    if sm['x']+sm['w']>256 or sm['y']+sm['h']>256:
        raise ToolError(f'Sample {si} rectangle runs outside its 256x256 texture page')
    page=wad['pages'][sm['page']]
    return [[page_pixel(page,sm['x']+x,sm['y']+y) for x in range(sm['w'])] for y in range(sm['h'])]


def write_bmp24(path: Path, width: int, height: int, get_pixel, scale=1):
    """Write a conservative Windows 3.x 24-bit BITMAPINFOHEADER BMP."""
    W=width*scale; H=height*scale
    stride=(W*3+3)&~3
    pix=bytearray(stride*H)
    # BMP rows are bottom-up.
    for oy in range(H):
        sy=(H-1-oy)//scale
        row=oy*stride
        for ox in range(W):
            sx=ox//scale
            r,g,b=get_pixel(sx,sy)
            o=row+ox*3
            pix[o:o+3]=bytes((b,g,r))
    off=54; size=off+len(pix)
    fh=b'BM'+struct.pack('<IHHI',size,0,0,off)
    ih=struct.pack('<IiiHHIIiiII',40,W,H,1,24,0,len(pix),2835,2835,0,0)
    path.write_bytes(fh+ih+pix)


# ---------- Portable image I/O for editable texture workspaces ----------
def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)


def write_png_rgb(path: Path, width: int, height: int, get_pixel, scale=1):
    """Write an 8-bit RGB PNG using only the Python standard library."""
    W=width*scale; H=height*scale
    rows=[]
    for y in range(H):
        sy=y//scale
        row=bytearray([0])  # PNG filter type 0
        for x in range(W):
            sx=x//scale
            row.extend(bytes(get_pixel(sx,sy)))
        rows.append(bytes(row))
    raw=b''.join(rows)
    png=(b'\x89PNG\r\n\x1a\n'+
         _png_chunk(b'IHDR',struct.pack('>IIBBBBB',W,H,8,2,0,0,0))+
         _png_chunk(b'IDAT',zlib.compress(raw,9))+
         _png_chunk(b'IEND',b''))
    path.write_bytes(png)


def write_png_rgba(path: Path, width: int, height: int, get_pixel, scale=1):
    """Write an 8-bit RGBA PNG using only the Python standard library."""
    W=width*scale; H=height*scale
    rows=[]
    for y in range(H):
        sy=y//scale
        row=bytearray([0])
        for x in range(W):
            sx=x//scale
            row.extend(bytes(get_pixel(sx,sy)))
        rows.append(bytes(row))
    raw=b''.join(rows)
    png=(b'\x89PNG\r\n\x1a\n'+
         _png_chunk(b'IHDR',struct.pack('>IIBBBBB',W,H,8,6,0,0,0))+
         _png_chunk(b'IDAT',zlib.compress(raw,9))+
         _png_chunk(b'IEND',b''))
    path.write_bytes(png)


def _paeth(a,b,c):
    p=a+b-c; pa=abs(p-a); pb=abs(p-b); pc=abs(p-c)
    if pa<=pb and pa<=pc: return a
    if pb<=pc: return b
    return c


def read_png_rgb(path: Path, transparent=TRANSPARENT_DEFAULT):
    b=path.read_bytes()
    if not b.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ToolError('Not a PNG file')
    p=8; width=height=None; bitdepth=ctype=None; interlace=None; idat=[]
    while p+12<=len(b):
        n=struct.unpack_from('>I',b,p)[0]; kind=b[p+4:p+8]; data=b[p+8:p+8+n]; p+=12+n
        if kind==b'IHDR':
            width,height,bitdepth,ctype,comp,filt,interlace=struct.unpack('>IIBBBBB',data)
        elif kind==b'IDAT': idat.append(data)
        elif kind==b'IEND': break
    if width is None or bitdepth!=8 or ctype not in (2,6) or interlace!=0:
        raise ToolError('PNG importer supports non-interlaced 8-bit RGB/RGBA PNG only')
    channels=3 if ctype==2 else 4; stride=width*channels
    raw=zlib.decompress(b''.join(idat))
    if len(raw)!=(stride+1)*height:
        raise ToolError('PNG decompressed size does not match image dimensions')
    rows=[]; prev=bytearray(stride); q=0
    for _y in range(height):
        ft=raw[q]; q+=1; src=raw[q:q+stride]; q+=stride; cur=bytearray(stride)
        for i,x in enumerate(src):
            left=cur[i-channels] if i>=channels else 0
            up=prev[i]
            ul=prev[i-channels] if i>=channels else 0
            if ft==0: v=x
            elif ft==1: v=(x+left)&255
            elif ft==2: v=(x+up)&255
            elif ft==3: v=(x+((left+up)//2))&255
            elif ft==4: v=(x+_paeth(left,up,ul))&255
            else: raise ToolError(f'Unsupported PNG filter type {ft}')
            cur[i]=v
        row=[]
        for x in range(width):
            o=x*channels; rgb=tuple(cur[o:o+3])
            if channels==4 and cur[o+3]<128: rgb=transparent
            row.append(rgb)
        rows.append(row); prev=cur
    return width,height,rows


def read_bmp_rgb(path: Path, transparent=TRANSPARENT_DEFAULT):
    b=path.read_bytes()
    if len(b)<54 or b[:2]!=b'BM': raise ToolError('Not a BMP file')
    pixoff=u32(b,10); dib=u32(b,14)
    if dib<40: raise ToolError(f'Unsupported BMP DIB header size {dib}')
    width=i32(b,18); height=i32(b,22); planes=u16(b,26); bpp=u16(b,28); comp=u32(b,30)
    if planes!=1 or bpp not in (24,32) or comp!=0:
        raise ToolError('BMP importer supports uncompressed 24-bit or 32-bit BMP only')
    W=abs(width); H=abs(height); topdown=height<0; bytespp=bpp//8; stride=(W*bytespp+3)&~3
    if pixoff+stride*H>len(b): raise ToolError('BMP pixel data is truncated')
    # In BI_RGB 32-bit BMP files the fourth byte is historically allowed to be
    # unused and many editors write it as zero for every pixel. Treat alpha as
    # meaningful only when the file contains at least one nonzero alpha byte.
    meaningful_alpha=False
    if bytespp==4:
        for sy in range(H):
            base=pixoff+sy*stride
            if any(b[base+x*4+3] != 0 for x in range(W)):
                meaningful_alpha=True; break
    rows=[]
    for y in range(H):
        sy=y if topdown else H-1-y; base=pixoff+sy*stride; row=[]
        for x in range(W):
            o=base+x*bytespp; bb,gg,rr=b[o:o+3]
            if bytespp==4 and meaningful_alpha and b[o+3]<128: row.append(transparent)
            else: row.append((rr,gg,bb))
        rows.append(row)
    return W,H,rows


def read_edit_image(path: Path, transparent=TRANSPARENT_DEFAULT):
    path=Path(path)
    ext=path.suffix.lower()
    if ext=='.png': return read_png_rgb(path,transparent)
    if ext=='.bmp': return read_bmp_rgb(path,transparent)
    raise ToolError('Editable texture image must be .png or .bmp')


def flatten_rgb(rows):
    return bytes(v for row in rows for c in row for v in c)


# ---------- WAD-independent N-Gage texture workspace ----------
def parse_texture_descriptor(raw: bytes):
    if len(raw)!=16: raise ToolError('Texture descriptor must be 16 bytes')
    ws=struct.unpack('<4I',raw)
    uv=[(w&255,(w>>8)&255) for w in ws]
    cl=(ws[0]>>16)&0xffff; tp=(ws[1]>>16)&0xffff
    clxy=((cl&0x3f)*16,(cl>>6)&0x1ff)
    return {'words':ws,'uv':uv,'clut_raw':cl,'clut_xy':clxy,'tpage':tp}


def decode_tpa_indices(data: bytes):
    if len(data)!=32768: raise ToolError(f'Expected 32768-byte new_tpage.tpa, got {len(data)}')
    words=struct.unpack('<16384H',data); idx=[[0]*256 for _ in range(256)]
    for y in range(256):
        for xw in range(64):
            w=words[y*64+xw]; x=xw*4
            idx[y][x]=w&15; idx[y][x+1]=(w>>4)&15; idx[y][x+2]=(w>>8)&15; idx[y][x+3]=(w>>12)&15
    return idx,list(words)


def encode_tpa_indices(idx, words):
    out=list(words)
    for y in range(256):
        for xw in range(64):
            x=xw*4
            out[y*64+xw]=(idx[y][x]&15)|((idx[y][x+1]&15)<<4)|((idx[y][x+2]&15)<<8)|((idx[y][x+3]&15)<<12)
    return out


def tpa_palettes(words, bank='A'):
    base=241 if bank=='A' else 177
    return [list(words[(base+g)*64:(base+g)*64+16]) for g in range(15)]


def descriptor_usage(retexture_path: Path, lara_path: Path):
    b=retexture_path.read_bytes()
    if len(b)!=9006: raise ToolError(f'Expected 9006-byte known retexture.dat format, got {len(b)}')
    recs=parse_ngage_lara(lara_path); p=3232
    usage=[{'quad':0,'tri':0,'meshes':set()} for _ in range(101)]
    for r in recs:
        for f in r['quads']+r['triangles']:
            n=len(f['v']); need=n*2+2
            if p+need>len(b): raise ToolError('retexture.dat patch stream is truncated')
            code=u16(b,p+n*2); p+=need
            if code<=100:
                j=100-code; usage[j]['quad' if n==4 else 'tri']+=1; usage[j]['meshes'].add(r['name'])
    if p!=len(b): raise ToolError(f'retexture.dat patch stream stops at {p}, not exact EOF {len(b)}')
    A=[b[i*16:(i+1)*16] for i in range(101)]
    B=[b[1616+i*16:1616+(i+1)*16] for i in range(101)]
    return b,A,B,usage


def validate_descriptor_banks(A,B,usage):
    """Validate the paired A/B descriptor convention used by the known N-Gage outfit format.

    The editable RGB export renders bank A. For safe duplicate/preserve handling, active
    bank-B descriptors must address the same texture page/UV geometry and the corresponding
    CLUT group at B_BASE_Y + group.
    """
    differences=[]
    for j,(ra,rb,u) in enumerate(zip(A,B,usage)):
        if not (u['quad'] or u['tri']):
            continue
        a=parse_texture_descriptor(ra); b=parse_texture_descriptor(rb)
        ax,ay=a['clut_xy']; bx,by=b['clut_xy']
        ga=ay-A_BASE_Y; gb=by-B_BASE_Y
        if ax!=VRAM_X or bx!=VRAM_X or not (0<=ga<15) or not (0<=gb<15):
            raise ToolError(f'Descriptor {j} uses unsupported A/B CLUT locations {a["clut_xy"]} / {b["clut_xy"]}')
        if ga!=gb:
            raise ToolError(f'Descriptor {j} maps A palette group {ga} to B group {gb}; layered/independent bank editing is not supported yet')
        if a['tpage']!=b['tpage']:
            raise ToolError(f'Descriptor {j} uses different A/B texture pages 0x{a["tpage"]:04X}/0x{b["tpage"]:04X}')
        # The stock AoD file contains two known descriptors whose word-3 low half
        # differs between banks even though the normal/alternate palette-group pairing
        # is otherwise regular. Keep retexture.dat byte-exact and report such cases
        # instead of treating them as a fatal workspace-layout error.
        n=4 if u['quad'] else 3
        if a['uv'][:n]!=b['uv'][:n]:
            differences.append(j)
    return differences


def build_palette_map(A,usage):
    """Return 256x256 signed palette-group map. BBoxes do not cross palette groups in known files."""
    pm=[-1]*(256*256); rows=[]
    for j,(raw,u) in enumerate(zip(A,usage)):
        if not (u['quad'] or u['tri']): continue
        d=parse_texture_descriptor(raw); pts=list(d['uv'][:3])
        if u['quad']: pts.append(d['uv'][3])
        gx,gy=d['clut_xy']; group=gy-A_BASE_Y
        if gx!=VRAM_X or not (0<=group<15):
            raise ToolError(f'Descriptor {j} uses unsupported normal CLUT ({gx},{gy}); expected x={VRAM_X}, y={A_BASE_Y}..{A_BASE_Y+14}')
        xs=[q[0] for q in pts]; ys=[q[1] for q in pts]
        x0,x1=min(xs),max(xs); y0,y1=min(ys),max(ys)
        # We deliberately expose the full rectangular texture sample area. Known N-Gage
        # outfit descriptors never have cross-palette rectangle overlap.
        for y in range(y0,y1+1):
            for x in range(x0,x1+1):
                k=y*256+x
                if pm[k] not in (-1,group):
                    raise ToolError(f'Editable atlas has overlapping descriptors using palette groups {pm[k]} and {group} at ({x},{y}). This file needs layered export support.')
                # Embedded CLUT storage occupies x 0..63 on these row bands.
                if x<64 and (177<=y<=191 or 241<=y<=255):
                    raise ToolError(f'Descriptor {j} overlaps embedded CLUT storage at ({x},{y}); refusing unsafe editable export')
                pm[k]=group
        rows.append([j,100-j,u['quad'],u['tri'],group,x0,y0,x1,y1,';'.join(sorted(u['meshes']))])
    return pm,rows


def render_texture_rows(idx,palettes,pm,transparent=TRANSPARENT_DEFAULT,outside=(48,48,48)):
    rows=[]
    for y in range(256):
        row=[]
        for x in range(256):
            g=pm[y*256+x]
            if g<0:
                # Checkerboard so unused pixels are obvious in an editor.
                c=outside if ((x//8+y//8)&1)==0 else tuple(min(255,v+24) for v in outside)
            else:
                k=idx[y][x]; c=transparent if k==0 else psx_to_rgb(palettes[g][k])
            row.append(c)
        rows.append(row)
    return rows


def export_texture_workspace(tpa_path: Path, retexture_path: Path, lara_path: Path, out: Path,
                             transparent=TRANSPARENT_DEFAULT):
    out.mkdir(parents=True,exist_ok=True)
    tpa=tpa_path.read_bytes(); idx,words=decode_tpa_indices(tpa)
    rt,A,B,usage=descriptor_usage(retexture_path,lara_path)
    bank_uv_differences=validate_descriptor_banks(A,B,usage)
    pm,layout=build_palette_map(A,usage); pals=tpa_palettes(words,'A')
    rows=render_texture_rows(idx,pals,pm,transparent)
    ref=flatten_rgb(rows)
    (out/'template_new_tpage.tpa').write_bytes(tpa)
    (out/'template_retexture.dat').write_bytes(rt)
    (out/'palette_map.bin').write_bytes(bytes((v+1)&255 for v in pm)) # 0=unused, 1..15=groups 0..14
    (out/'texture_reference.rgb').write_bytes(ref)
    write_png_rgb(out/'texture_edit.png',256,256,lambda x,y:rows[y][x])
    write_png_rgb(out/'texture_edit_4x.png',256,256,lambda x,y:rows[y][x],4)
    write_bmp24(out/'texture_edit.bmp',256,256,lambda x,y:rows[y][x])
    write_png_rgb(out/'coverage_mask.png',256,256,lambda x,y:(255,255,255) if pm[y*256+x]>=0 else (0,0,0))
    group_colors=[
        (230, 70, 70),(70, 130, 230),(70, 190, 100),(230, 170, 60),(170, 90, 220),
        (60, 190, 190),(230, 90, 160),(140, 140, 70),(90, 100, 200),(190, 110, 60),
        (80, 170, 150),(200, 80, 110),(120, 180, 70),(160, 110, 180),(80, 150, 210)
    ]
    def gp(x,y):
        g=pm[y*256+x]
        if g<0:return (0,0,0)
        return group_colors[g]
    write_png_rgb(out/'palette_group_map.png',256,256,gp)
    with (out/'descriptor_layout.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['table_index','local_code','quad_uses','triangle_uses','palette_group','x0','y0','x1','y1','meshes']); w.writerows(layout)
    meta={
        'format':'TRNGAGE_TEXTURE_WORKSPACE_1','tool_version':VERSION,'width':256,'height':256,
        'transparent_rgb':list(transparent),'source_tpa_sha256':sha256(tpa),'source_retexture_sha256':sha256(rt),
        'palette_map_sha256':sha256((out/'palette_map.bin').read_bytes()),'reference_rgb_sha256':sha256(ref),
        'descriptor_bank_validation':'paired A/B palette-group + TPAGE convention validated; retexture.dat is preserved byte-exact',
        'a_b_uv_difference_descriptors':bank_uv_differences,
        'covered_pixels':sum(v>=0 for v in pm),'active_palette_groups':sorted(set(v for v in pm if v>=0)),
        'edit_file':'texture_edit.png','template_tpa':'template_new_tpage.tpa','template_retexture':'template_retexture.dat',
        'notes':'Edit texture_edit.png or texture_edit.bmp. Checkerboard/unused pixels are ignored on import. Pure magenta (255,0,255) inside used regions means transparent index 0.'
    }
    (out/'workspace.json').write_text(json.dumps(meta,indent=2)+'\n')
    (out/'README-EDIT-TEXTURES.txt').write_text(
        'TR N-Gage editable texture workspace\n\n'
        'Edit texture_edit.png (preferred) or texture_edit.bmp in your photo editor.\n'
        'DO NOT resize the image: it must stay exactly 256x256.\n'
        'Only the non-checkerboard regions are used by Lara. coverage_mask.png shows them in white.\n'
        'Pure magenta RGB 255,0,255 inside a used region is treated as transparent.\n\n'
        'When finished, use Import Texture Workspace in the GUI or:\n'
        '  python tr_ngage_outfit.py import-textures THIS_FOLDER --image texture_edit.png -o output\n\n'
        'The importer automatically converts full RGB artwork back to the N-Gage 4-bpp/16-color-per-group format.\n'
        'It keeps the existing UV/face mapping, so no WAD is needed after this workspace has been exported.\n'
    )
    return meta


def weighted_median_cut(hist,limit=15):
    """Weighted median-cut over PSX 5-bit RGB words. Returns up to limit representative words."""
    if not hist: return [rgb_to_psx((1,1,1))]
    if len(hist)<=limit: return [w for w,_ in hist.most_common(limit)]
    def rgb5(w): return (w&31,(w>>5)&31,(w>>10)&31)
    boxes=[list(hist.items())]
    while len(boxes)<limit:
        best_i=None; best_score=-1; best_ch=0
        for i,box in enumerate(boxes):
            if len(box)<=1: continue
            cols=[rgb5(w) for w,_ in box]; ranges=[max(c[k] for c in cols)-min(c[k] for c in cols) for k in range(3)]
            ch=max(range(3),key=lambda k:ranges[k]); score=ranges[ch]*sum(n for _,n in box)
            if score>best_score: best_score=score; best_i=i; best_ch=ch
        if best_i is None: break
        box=boxes.pop(best_i); box.sort(key=lambda wn:rgb5(wn[0])[best_ch]); total=sum(n for _,n in box); acc=0; cut=1
        for k,(_,n) in enumerate(box[:-1],1):
            acc+=n
            if acc>=total/2: cut=k; break
        boxes.extend([box[:cut],box[cut:]])
    reps=[]
    for box in boxes:
        total=sum(n for _,n in box); vals=[rgb5(w) for w,_ in box]
        r=round(sum(c[0]*n for c,(_,n) in zip(vals,box))/total)
        g=round(sum(c[1]*n for c,(_,n) in zip(vals,box))/total)
        b=round(sum(c[2]*n for c,(_,n) in zip(vals,box))/total)
        w=(int(r)&31)|((int(g)&31)<<5)|((int(b)&31)<<10)
        if w==0:w=1|(1<<5)|(1<<10)
        if w not in reps: reps.append(w)
    # Fill any lost duplicate representatives with frequent source colors.
    for w,_ in hist.most_common():
        if w and w not in reps: reps.append(w)
        if len(reps)>=limit: break
    return reps[:limit]


def import_texture_workspace(workspace: Path, image_path: Path|None, out: Path,
                             alternate_mode='duplicate'):
    meta_path=workspace/'workspace.json'
    if not meta_path.is_file(): raise ToolError('workspace.json not found in texture workspace')
    meta=json.loads(meta_path.read_text())
    if meta.get('format')!='TRNGAGE_TEXTURE_WORKSPACE_1': raise ToolError('Unsupported texture workspace format')
    tpa_path=workspace/meta['template_tpa']; rt_path=workspace/meta['template_retexture']; pm_path=workspace/'palette_map.bin'; ref_path=workspace/'texture_reference.rgb'
    tpa=tpa_path.read_bytes(); rt=rt_path.read_bytes(); pmb=pm_path.read_bytes(); ref=ref_path.read_bytes()
    if (sha256(tpa)!=meta['source_tpa_sha256'] or sha256(rt)!=meta['source_retexture_sha256'] or
        sha256(pmb)!=meta['palette_map_sha256'] or sha256(ref)!=meta.get('reference_rgb_sha256')):
        raise ToolError('Workspace template/hash validation failed; one of the metadata/template/reference files was changed')
    if len(pmb)!=65536 or len(ref)!=256*256*3: raise ToolError('Workspace map/reference data has wrong size')
    pm=[v-1 for v in pmb]
    trans=tuple(meta.get('transparent_rgb',TRANSPARENT_DEFAULT))
    image_path=image_path or workspace/meta.get('edit_file','texture_edit.png')
    W,H,rows=read_edit_image(image_path,trans)
    if (W,H)!=(256,256): raise ToolError(f'Edited texture must remain 256x256; got {W}x{H}')
    rgb=flatten_rgb(rows); out.mkdir(parents=True,exist_ok=True)
    # True no-edit round trip is deliberately byte-exact.
    if rgb==ref:
        (out/'new_tpage.tpa').write_bytes(tpa); (out/'retexture.dat').write_bytes(rt)
        summary={'tool':'TR N-Gage Outfit Tool','version':VERSION,'mode':'texture_workspace_import','edited':False,
                 'note':'Image pixels are unchanged; original TPA and retexture.dat copied byte-for-byte.',
                 'sha256_tpa':sha256(tpa),'sha256_retexture':sha256(rt)}
    else:
        idx,words=decode_tpa_indices(tpa); groups=sorted(set(g for g in pm if g>=0))
        newpals={}; mse_total=0; opaque_total=0
        for g in groups:
            hist=Counter()
            for y in range(256):
                for x in range(256):
                    if pm[y*256+x]!=g: continue
                    c=rows[y][x]
                    if c!=trans: hist[rgb_to_psx(c)]+=1
            reps=weighted_median_cut(hist,15); pal=[0]+reps
            while len(pal)<16: pal.append(reps[0] if reps else rgb_to_psx((1,1,1)))
            newpals[g]=pal[:16]
            prgb=[psx_to_rgb(w) for w in pal[:16]]
            for y in range(256):
                for x in range(256):
                    if pm[y*256+x]!=g: continue
                    c=rows[y][x]
                    if c==trans: idx[y][x]=0; continue
                    k=min(range(1,16),key=lambda z:sum((c[j]-prgb[z][j])**2 for j in range(3)))
                    idx[y][x]=k; mse_total+=sum((c[j]-prgb[k][j])**2 for j in range(3)); opaque_total+=1
        words=encode_tpa_indices(idx,words)
        # CLUTs are embedded in the uploaded VRAM block.
        for g,pal in newpals.items():
            a=(241+g)*64; words[a:a+16]=pal
            if alternate_mode=='duplicate':
                b=(177+g)*64; words[b:b+16]=pal
            elif alternate_mode=='preserve':
                pass
            else: raise ToolError('alternate_mode must be duplicate or preserve')
        new_tpa=struct.pack('<16384H',*words)
        (out/'new_tpage.tpa').write_bytes(new_tpa); (out/'retexture.dat').write_bytes(rt)
        # Quantized preview using normal bank.
        qidx,_=decode_tpa_indices(new_tpa); qp=tpa_palettes(list(struct.unpack('<16384H',new_tpa)),'A')
        qrows=render_texture_rows(qidx,qp,pm,trans)
        write_png_rgb(out/'imported_preview.png',256,256,lambda x,y:qrows[y][x])
        write_png_rgb(out/'imported_preview_4x.png',256,256,lambda x,y:qrows[y][x],4)
        # Diagnostic mask: white = covered pixel whose editable RGB value changed.
        def diffp(x,y):
            k=(y*256+x)*3
            changed=(pm[y*256+x]>=0 and bytes(rows[y][x])!=ref[k:k+3])
            return (255,255,255) if changed else (0,0,0)
        write_png_rgb(out/'edit_diff_mask.png',256,256,diffp)
        mse=mse_total/(max(1,opaque_total)*3)
        summary={'tool':'TR N-Gage Outfit Tool','version':VERSION,'mode':'texture_workspace_import','edited':True,
                 'alternate_palette_mode':alternate_mode,'covered_pixels':sum(g>=0 for g in pm),
                 'changed_covered_pixels':sum(1 for y in range(256) for x in range(256) if pm[y*256+x]>=0 and bytes(rows[y][x])!=ref[(y*256+x)*3:(y*256+x)*3+3]),
                 'active_palette_groups':groups,
                 'quantization_mse_rgb_channel':mse,'sha256_tpa':sha256(new_tpa),'sha256_retexture':sha256(rt)}
    (out/'import_manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    (out/'INSTALL.txt').write_text(
        'TR N-Gage edited texture output\n\nBACK UP YOUR ORIGINAL FILES FIRST.\n\n'
        'Copy new_tpage.tpa and retexture.dat to:\nE:\\System\\Apps\\tombraider\\data\\deldata\\\n\n'
        'This texture-workspace mode keeps the existing Lara mesh and UV/face mapping.\n'
    )
    return summary


# ---------- Palette / descriptor ----------
def rgb_to_psx(c):
    r,g,b=c
    r5=int(round(r*31/255)); g5=int(round(g*31/255)); b5=int(round(b*31/255))
    if r5==g5==b5==0: r5=g5=b5=1
    return r5 | (g5<<5) | (b5<<10)


def psx_to_rgb(w):
    cv=lambda v:(v<<3)|(v>>2)
    return (cv(w&31),cv((w>>5)&31),cv((w>>10)&31))


def clut_raw(x,y): return ((y&0x1ff)<<6)|((x>>4)&0x3f)


def make_desc(uv,group,bank):
    q=list(uv)+[(0,0)]*(4-len(uv))
    cy=(A_BASE_Y if bank=='A' else B_BASE_Y)+group
    ws=[0,0,0,0]
    ws[0]=(clut_raw(VRAM_X,cy)<<16) | ((q[0][1]&255)<<8) | (q[0][0]&255)
    ws[1]=(TPAGE<<16) | ((q[1][1]&255)<<8) | (q[1][0]&255)
    ws[2]=(0x343C<<16) | ((q[2][1]&255)<<8) | (q[2][0]&255)
    ws[3]=((q[3][1]&255)<<8) | (q[3][0]&255)
    return struct.pack('<4I',*ws)


# ---------- WAD2 / Tomb Editor ----------
def score_wad2_candidate(wad, ng, moveable):
    if len(moveable.get('meshes',[]))!=15: return None
    vertex_count_matches=0; topology_matches=0; topology_total=0; exact_position_meshes=0
    for mi,mesh in enumerate(moveable['meshes']):
        if len(mesh['positions'])==abs(ng[mi]['vertex_count']): vertex_count_matches+=1
        # Tomb Editor Lara uses opposite vertical sign relative to the decoded N-Gage mesh.
        if len(mesh['positions'])==abs(ng[mi]['vertex_count']):
            npos=[tuple(v[:3]) for v in ng[mi]['positions']]
            ypos=[(round(v[0]),round(-v[1]),round(v[2])) for v in mesh['positions']]
            if ypos==npos: exact_position_meshes+=1
        by=Counter((len(p['v']),canon(p['v'])) for p in mesh['polygons'])
        for f in ng[mi]['quads']+ng[mi]['triangles']:
            topology_total+=1; k=(len(f['v']),canon(f['v']))
            if by[k]: topology_matches+=1; by[k]-=1
    coverage=topology_matches/max(1,topology_total)
    if coverage>=0.80 and vertex_count_matches>=13:
        grade='A'; mode='texture-convert-supported'
    elif coverage>=0.70 and vertex_count_matches>=10:
        grade='B'; mode='texture-convert-with-fallback'
    else:
        grade='C'; mode='geometry-replacement-required'
    role_hint={0:'LARA / animation-skeleton',12:'LARA_SKIN',14:'LARA_SCREAM'}.get(moveable['object_id'],'unknown')
    return {'object_id':moveable['object_id'],'role_hint':role_hint,'moveable':moveable,'vertex_count_matches':vertex_count_matches,
            'exact_position_meshes_after_y_flip':exact_position_meshes,'topology_matches':topology_matches,
            'topology_total':topology_total,'topology_coverage':coverage,'grade':grade,'recommended_mode':mode,
            'used_textures':sorted(set(p['texture'] for m in moveable['meshes'] for p in m['polygons'])),
            'score':topology_matches*100+vertex_count_matches*2+exact_position_meshes}


def find_wad2_lara_skin(wad, ng, object_id=None, require_convertible=False):
    candidates=[]
    for m in wad.get('moveables',[]):
        if object_id is not None and m['object_id']!=object_id: continue
        c=score_wad2_candidate(wad,ng,m)
        if c: candidates.append(c)
    if not candidates:
        if object_id is not None: raise ToolError(f'WAD2 object {object_id} is not a 15-mesh Lara candidate')
        raise ToolError('No 15-mesh WAD2 Lara candidate was found')
    # TombEngine/Tomb Editor game version 18 uses object 12 for LARA_SKIN. Prefer it when present;
    # object 14 is LARA_SCREAM and object 0 is the animation/skeleton object, which can otherwise
    # accidentally score higher on a few placeholder faces. Explicit --object-id always wins.
    if object_id is None:
        skin=[c for c in candidates if c['object_id']==12]
        best=max(skin,key=lambda c:c['score']) if skin else max(candidates,key=lambda c:c['score'])
    else:
        best=max(candidates,key=lambda c:c['score'])
    if require_convertible and best['recommended_mode']=='geometry-replacement-required':
        raise ToolError('Best WAD2 Lara candidate requires geometry replacement rather than the v0.3 texture-only path: '
                        f'object {best["object_id"]}, {best["topology_matches"]}/{best["topology_total"]} topology matches '
                        f'({best["topology_coverage"]:.1%}), {best["vertex_count_matches"]}/15 vertex-count matches. '
                        'Use analyze-wad2/export-wad2-model; geometry conversion is the next development branch.')
    return best


def analyze_wad2_file(wad2_path: Path, lara_path: Path, object_id=None):
    try: w=wad2.load(wad2_path)
    except wad2.WAD2Error as e: raise ToolError(str(e))
    ng=parse_ngage_lara(lara_path)
    allc=[]
    for m in w['moveables']:
        if len(m.get('meshes',[]))==15:
            c=score_wad2_candidate(w,ng,m)
            if c:
                allc.append({k:v for k,v in c.items() if k not in ('moveable','score')})
    best=find_wad2_lara_skin(w,ng,object_id)
    return {'tool':'TR N-Gage Outfit Tool','version':VERSION,'mode':'wad2_analysis','file':str(wad2_path),
            'wad2_sha256':sha256(wad2_path.read_bytes()),'container_version':w['version'],
            'suggested_game_version':w.get('suggested_game_version'),'texture_count':len(w['textures']),
            'moveable_count':len(w['moveables']),'selected_object_id':best['object_id'],'selected_role_hint':best['role_hint'],'selected_grade':best['grade'],
            'recommended_mode':best['recommended_mode'],'selected_topology_matches':best['topology_matches'],
            'selected_topology_total':best['topology_total'],'selected_topology_coverage':best['topology_coverage'],
            'selected_vertex_count_matches':best['vertex_count_matches'],
            'selected_exact_position_meshes_after_y_flip':best['exact_position_meshes_after_y_flip'],
            'selected_used_textures':best['used_textures'],'candidates':allc}


def _wad2_face_match(candidate, ng):
    """Return {(mesh,face): mapping}. UVs are reordered to the N-Gage face vertex order."""
    matches={}; rows=[]
    for mi,mesh in enumerate(candidate['moveable']['meshes']):
        by=defaultdict(list)
        for bi,p in enumerate(mesh['polygons']): by[(len(p['v']),canon(p['v']))].append((bi,p))
        for ni,nf in enumerate(ng[mi]['quads']+ng[mi]['triangles']):
            c=by.get((len(nf['v']),canon(nf['v'])),[])
            if not c:
                rows.append([mi,PRIMARY_NAMES[mi],ni,len(nf['v']),'','','',False]); continue
            bi,sp=c[0]
            if len(set(sp['v']))!=len(sp['v']):
                rows.append([mi,PRIMARY_NAMES[mi],ni,len(nf['v']),bi,sp['texture'],'duplicate-source-vertex',False]); continue
            uv_by_vertex={v:uv for v,uv in zip(sp['v'],sp['uvs'])}
            if any(v not in uv_by_vertex for v in nf['v']):
                rows.append([mi,PRIMARY_NAMES[mi],ni,len(nf['v']),bi,sp['texture'],'vertex-map-failed',False]); continue
            ordered=[uv_by_vertex[v] for v in nf['v']]
            matches[(mi,ni)]={'source_face_index':bi,'face':sp,'texture':sp['texture'],'uvs':ordered}
            rows.append([mi,PRIMARY_NAMES[mi],ni,len(nf['v']),bi,sp['texture'],'',True])
    return matches,rows


def _wad2_region_for_face(texture, uvs):
    # WAD2 UVs are pixel-space floats. Edge values equal to width/height occur in some modern assets;
    # clamp to the addressable 0..255-style texel domain when making N-Gage descriptors.
    pts=[]
    for u,v in uvs:
        x=max(0,min(texture['width']-1,int(round(u))))
        y=max(0,min(texture['height']-1,int(round(v))))
        pts.append((x,y))
    x0=min(x for x,y in pts); y0=min(y for x,y in pts); x1=max(x for x,y in pts); y1=max(y for x,y in pts)
    return (x0,y0,x1,y1),pts


def _pack_rectangles(rects):
    """Shelf pack {key:(w,h)} into 256 x safe-pixel-height."""
    order=sorted(((h,w,key) for key,(w,h) in rects.items()),reverse=True)
    shelves=[]; placement={}
    for h,w,key in order:
        if w>256 or h>PIXEL_REGION_MAX_Y: raise ToolError(f'WAD2 texture region {key} is too large for the N-Gage atlas: {w}x{h}')
        candidates=[]
        for i,sh in enumerate(shelves):
            if h<=sh['h'] and sh['x']+w<=256: candidates.append((sh['h']-h,sh['x'],i))
        if candidates:
            _,_,i=min(candidates); sh=shelves[i]; x=sh['x']; y=sh['y']; sh['x']+=w
        else:
            y=sum(sh['h'] for sh in shelves); sh={'y':y,'h':h,'x':w}; shelves.append(sh); x=0
        placement[key]=(x,y)
    total=sum(sh['h'] for sh in shelves)
    if total>PIXEL_REGION_MAX_Y:
        raise ToolError(f'WAD2 matched texture regions need {total} atlas rows; v0.3 safe region is {PIXEL_REGION_MAX_Y}. '
                        'This outfit needs atlas optimization or geometry/UV authoring.')
    return placement,total


def _wad2_uniform_source_color(w, used_texture_ids, alpha_threshold=128):
    """Return the single PSX BGR555 color if all used WAD2 textures are fully opaque and uniform.

    This is useful for Gold/Midas-style skins: topology does not matter when every polygon
    samples exactly the same color, so unmatched primary and weapon-variant faces can safely
    receive the same descriptor instead of falling back to Classic textures.
    """
    colors=set()
    for ti in sorted(used_texture_ids):
        tex=wad2.texture_by_index(w,ti)
        for y in range(tex['height']):
            for x in range(tex['width']):
                r,g,b,a=wad2.pixel_rgba(tex,x,y)
                if a < alpha_threshold:
                    return None
                colors.add(rgb_to_psx((r,g,b)))
                if len(colors)>1:
                    return None
    return next(iter(colors)) if len(colors)==1 else None


def convert_wad2(wad2_path: Path, lara_path: Path, out: Path, object_id=None, alpha_threshold=128, fallback_mode="auto"):
    """Convert a topology-compatible Tomb Editor WAD2 LARA_SKIN to TPA + retexture.dat."""
    try: w=wad2.load(wad2_path)
    except wad2.WAD2Error as e: raise ToolError(str(e))
    ng=parse_ngage_lara(lara_path); cand=find_wad2_lara_skin(w,ng,object_id,True)
    matches,match_rows=_wad2_face_match(cand,ng)
    if not matches: raise ToolError('No WAD2 faces could be mapped to the N-Gage Lara topology')
    tex_by_id={t['index']:t for t in w['textures']}
    # Build unique source rectangles. Faces with the same source texture/bbox share one packed patch.
    regions={}; face_region={}; face_srcpts={}
    used_textures=set()
    for key,m in matches.items():
        if m['texture'] not in tex_by_id: raise ToolError(f'WAD2 face refers to missing texture {m["texture"]}')
        tex=tex_by_id[m['texture']]; bbox,pts=_wad2_region_for_face(tex,m['uvs'])
        rkey=(m['texture'],)+bbox; regions.setdefault(rkey,(bbox[2]-bbox[0]+1,bbox[3]-bbox[1]+1))
        face_region[key]=rkey; face_srcpts[key]=pts; used_textures.add(m['texture'])
    if len(used_textures)>MAX_PALETTES:
        raise ToolError(f'WAD2 Lara uses {len(used_textures)} source textures; v0.3 maps one CLUT group per source texture and supports {MAX_PALETTES}.')
    if fallback_mode not in ('auto','classic','uniform'):
        raise ToolError('WAD2 fallback mode must be auto, classic, or uniform')
    uniform_color=_wad2_uniform_source_color(w,used_textures,alpha_threshold)
    if fallback_mode=='uniform' and uniform_color is None:
        raise ToolError('Uniform fallback was requested, but the selected WAD2 skin is not a single fully-opaque color')
    complete_uniform = (fallback_mode=='uniform') or (fallback_mode=='auto' and uniform_color is not None)
    placement,pack_h=_pack_rectangles(regions)
    texture_group={ti:i for i,ti in enumerate(sorted(used_textures))}
    # One 15-color median-cut palette per used source texture.
    hist_by_tex={ti:Counter() for ti in used_textures}
    # Avoid counting the same source region repeatedly.
    for rkey in regions:
        ti,x0,y0,x1,y1=rkey; tex=tex_by_id[ti]
        for y in range(y0,y1+1):
            for x in range(x0,x1+1):
                r,g,b,a=wad2.pixel_rgba(tex,x,y)
                if a>=alpha_threshold: hist_by_tex[ti][rgb_to_psx((r,g,b))]+=1
    palettes=[]; rgbp=[]
    for ti in sorted(used_textures):
        reps=weighted_median_cut(hist_by_tex[ti],15); pal=[0]+reps
        while len(pal)<16: pal.append(reps[0] if reps else rgb_to_psx((1,1,1)))
        palettes.append(pal[:16]); rgbp.append([psx_to_rgb(z) if i else (0,0,0) for i,z in enumerate(pal[:16])])
    while len(palettes)<MAX_PALETTES:
        palettes.append(list(palettes[0])); rgbp.append(list(rgbp[0]))
    idx=[[0]*256 for _ in range(256)]; mse_total=0; opaque=0
    # Copy each unique source region once, quantized by its source-texture palette.
    for rkey,(rw,rh) in regions.items():
        ti,x0,y0,x1,y1=rkey; dx,dy=placement[rkey]; g=texture_group[ti]; tex=tex_by_id[ti]; prgb=rgbp[g]
        for sy in range(y0,y1+1):
            for sx in range(x0,x1+1):
                r,gc,b,a=wad2.pixel_rgba(tex,sx,sy); tx=dx+(sx-x0); ty=dy+(sy-y0)
                if a<alpha_threshold: idx[ty][tx]=0; continue
                c=(r,gc,b); k=min(range(1,16),key=lambda z:sum((c[j]-prgb[z][j])**2 for j in range(3)))
                idx[ty][tx]=k; mse_total+=sum((c[j]-prgb[k][j])**2 for j in range(3)); opaque+=1
    words=[]
    for y in range(256):
        for xw in range(64):
            x=xw*4; words.append(idx[y][x]|(idx[y][x+1]<<4)|(idx[y][x+2]<<8)|(idx[y][x+3]<<12))
    for g in range(MAX_PALETTES):
        for local_y in (177+g,241+g):
            base=local_y*64; words[base:base+16]=palettes[g]
    tpa=struct.pack('<16384H',*words)
    # Create descriptors; leave N-Gage vertex order untouched.
    desc_keys=[]; key_to_code={}; face_code={}
    for fkey,m in matches.items():
        rkey=face_region[fkey]; ti,x0,y0,x1,y1=rkey; dx,dy=placement[rkey]; pts=face_srcpts[fkey]
        uv=tuple((dx+(x-x0),dy+(y-y0)) for x,y in pts); pg=texture_group[ti]
        dkey=(len(uv),uv,pg)
        if dkey not in key_to_code:
            if len(desc_keys)>=MAX_DESCRIPTORS:
                raise ToolError(f'WAD2 conversion needs more than {MAX_DESCRIPTORS} unique N-Gage descriptors')
            key_to_code[dkey]=len(desc_keys); desc_keys.append(dkey)
        face_code[fkey]=key_to_code[dkey]
    def safe_unused(bank): return make_desc([(0,0)]*4,0,bank)
    A=[safe_unused('A') for _ in range(MAX_DESCRIPTORS)]; B=[safe_unused('B') for _ in range(MAX_DESCRIPTORS)]
    for dkey,code in key_to_code.items():
        n,uv,pg=dkey; j=100-code; A[j]=make_desc(list(uv),pg,'A'); B[j]=make_desc(list(uv),pg,'B')
    stream=bytearray(); patch_rows=[]
    # If the entire source skin is one fully opaque color (for example Gold/Midas Lara),
    # topology/UV differences no longer matter. Reuse descriptor code 0 for every unmatched
    # primary face and all 11 weapon/holster variant meshes. This prevents Classic patches
    # from showing through on the head, torso, thighs, holsters, etc.
    uniform_fill_code = 0 if complete_uniform and desc_keys else None
    for mi,r in enumerate(ng):
        for ni,f in enumerate(r['quads']+r['triangles']):
            code=face_code.get((mi,ni))
            if code is not None:
                action='wad2'
            elif uniform_fill_code is not None:
                code=uniform_fill_code; action='wad2_uniform_fill'
            else:
                code=0xFFFF; action='classic_fallback'
            verts=f['v']
            stream+=struct.pack('<'+'H'*len(verts),*verts)+struct.pack('<H',code)
            patch_rows.append([mi,r['name'],'quad' if len(verts)==4 else 'triangle',ni,' '.join(map(str,verts)),code,action])
    rt=b''.join(A)+b''.join(B)+bytes(stream)
    if len(rt)!=9006: raise ToolError(f'Generated WAD2 retexture.dat is {len(rt)} bytes, expected 9006')
    out.mkdir(parents=True,exist_ok=True); (out/'new_tpage.tpa').write_bytes(tpa); (out/'retexture.dat').write_bytes(rt)
    with (out/'face_mapping.csv').open('w',newline='') as f:
        wr=csv.writer(f); wr.writerow(['mesh_index','mesh_name','ngage_face_index','vertices','source_face_index','source_texture','note','matched']); wr.writerows(match_rows)
    with (out/'patch_summary.csv').open('w',newline='') as f:
        wr=csv.writer(f); wr.writerow(['mesh_index','mesh_name','face_type','face_index','replacement_vertices','local_code','action']); wr.writerows(patch_rows)
    with (out/'atlas_layout.csv').open('w',newline='') as f:
        wr=csv.writer(f); wr.writerow(['source_texture','src_x0','src_y0','src_x1','src_y1','width','height','dst_x','dst_y','palette_group'])
        for rkey,(rw,rh) in sorted(regions.items()):
            ti,x0,y0,x1,y1=rkey; dx,dy=placement[rkey]; wr.writerow([ti,x0,y0,x1,y1,rw,rh,dx,dy,texture_group[ti]])
    def preview_pixel(x,y):
        k=idx[y][x]
        if k==0:return TRANSPARENT_DEFAULT
        pg=0
        for rkey,(rw,rh) in regions.items():
            dx,dy=placement[rkey]
            if dx<=x<dx+rw and dy<=y<dy+rh: pg=texture_group[rkey[0]]; break
        return rgbp[pg][k]
    write_png_rgb(out/'atlas_preview.png',256,256,preview_pixel); write_png_rgb(out/'atlas_preview_4x.png',256,256,preview_pixel,4)
    primary_total=sum(len(ng[i]['quads'])+len(ng[i]['triangles']) for i in range(15)); mapped=len(matches)
    manifest={'tool':'TR N-Gage Outfit Tool','version':VERSION,'mode':'wad2_texture_conversion',
              'source_wad2':str(wad2_path),'source_wad2_sha256':sha256(wad2_path.read_bytes()),
              'selected_object_id':cand['object_id'],'compatibility_grade':cand['grade'],
              'topology_coverage':cand['topology_coverage'],'vertex_count_matches':cand['vertex_count_matches'],
              'mapped_primary_faces':mapped,'primary_faces':primary_total,
              'primary_fallback_faces':0 if complete_uniform else primary_total-mapped,
              'uniform_source_completion':bool(complete_uniform),
              'uniform_source_psx_color':(f'0x{uniform_color:04X}' if uniform_color is not None else None),
              'fallback_mode':fallback_mode,
              'weapon_extra_faces_fallback':0 if complete_uniform else sum(len(ng[i]['quads'])+len(ng[i]['triangles']) for i in range(15,26)),
              'used_source_textures':sorted(used_textures),'palette_groups_used':len(used_textures),
              'unique_packed_regions':len(regions),'packed_height':pack_h,'descriptor_count':len(desc_keys),
              'quantization_mse_rgb_channel':mse_total/(max(1,opaque)*3),'tpa_size':len(tpa),'retexture_size':len(rt),
              'sha256_tpa':sha256(tpa),'sha256_retexture':sha256(rt),
              'note':'v0.3.1 WAD2 mode remains texture/topology conversion only. Uniform single-color skins can now safely complete unmatched primary and weapon-variant faces without geometry replacement.'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'INSTALL.txt').write_text('TR N-Gage WAD2 texture conversion output\n\nBACK UP ORIGINALS FIRST.\n\nCopy new_tpage.tpa and retexture.dat to:\nE:\\System\\Apps\\tombraider\\data\\deldata\\\n\nLeave lara.mesh unchanged. Test an early normal level unarmed first.\n')
    return manifest


def export_wad2_model(wad2_path: Path, lara_path: Path, out: Path, object_id=None):
    """Export best 15-mesh WAD2 Lara candidate as OBJ parts + source textures for geometry work."""
    try:w=wad2.load(wad2_path)
    except wad2.WAD2Error as e:raise ToolError(str(e))
    ng=parse_ngage_lara(lara_path); cand=find_wad2_lara_skin(w,ng,object_id,False); mov=cand['moveable']
    out.mkdir(parents=True,exist_ok=True); tdir=out/'textures'; odir=out/'parts'; tdir.mkdir(exist_ok=True); odir.mkdir(exist_ok=True)
    texids=sorted(set(p['texture'] for m in mov['meshes'] for p in m['polygons']))
    texmap={t['index']:t for t in w['textures']}
    for ti in texids:
        if ti not in texmap:continue
        t=texmap[ti]
        write_png_rgba(tdir/f'texture_{ti:03d}.png',t['width'],t['height'],lambda x,y,t=t:wad2.pixel_rgba(t,x,y))
    mtl=['# TR N-Gage Outfit Tool WAD2 source materials']
    for ti in texids:
        if ti in texmap:
            mtl += [f'newmtl texture_{ti}', 'Kd 1 1 1', f'map_Kd textures/texture_{ti:03d}.png','']
    (out/'lara_wad2.mtl').write_text('\n'.join(mtl)+'\n')
    rows=[]
    for mi,mesh in enumerate(mov['meshes']):
        name=PRIMARY_NAMES[mi]; lines=[f'# WAD2 object {cand["object_id"]} mesh {mi}: {name}','mtllib ../lara_wad2.mtl',f'o {name}']
        for x,y,z in mesh['positions']: lines.append(f'v {x:.6f} {y:.6f} {z:.6f}')
        vt=1; faces=[]
        for p in mesh['polygons']:
            tex=texmap.get(p['texture']); local=[]
            for u,v in p['uvs']:
                if tex: uu=u/max(1,tex['width']); vv=1.0-v/max(1,tex['height'])
                else: uu=vv=0.0
                lines.append(f'vt {uu:.9f} {vv:.9f}'); local.append(vt); vt+=1
            faces.append((p,local))
        cur=None
        for p,vts in faces:
            if p['texture']!=cur:cur=p['texture'];lines.append(f'usemtl texture_{cur}')
            refs=[f'{vi+1}/{ti}' for vi,ti in zip(p['v'],vts)]; lines.append('f '+' '.join(refs))
        (odir/f'{mi:02d}_{name}.obj').write_text('\n'.join(lines)+'\n')
        rows.append({'index':mi,'name':name,'source_mesh_name':mesh.get('name',''),'vertices':len(mesh['positions']),
                     'faces':len(mesh['polygons']),'textures':sorted(set(p['texture'] for p in mesh['polygons'])),
                     'ngage_vertices':abs(ng[mi]['vertex_count']),'ngage_faces':len(ng[mi]['quads'])+len(ng[mi]['triangles'])})
    manifest={'tool':'TR N-Gage Outfit Tool','version':VERSION,'mode':'wad2_model_export','source_wad2':str(wad2_path),
              'selected_object_id':cand['object_id'],'compatibility_grade':cand['grade'],'recommended_mode':cand['recommended_mode'],
              'topology_coverage':cand['topology_coverage'],'vertex_count_matches':cand['vertex_count_matches'],
              'used_textures':texids,'bones':mov.get('bones',[]),'meshes':rows,
              'geometry_note':'OBJ parts are exported in WAD2 mesh-local coordinates. v0.3 does not synthesize a replacement lara.mesh.'}
    (out/'model_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'README.txt').write_text('WAD2 Lara geometry-development export\n\nThe 15 primary Lara meshes are under parts/. Source textures are under textures/.\nThis is an analysis/editing export, NOT an installable N-Gage lara.mesh. See docs/WAD2-GEOMETRY-LAB.md.\n')
    return manifest

# ---------- Experimental WAD2 geometry serializer (v0.4) ----------
def _round_i16(v, label):
    n=int(round(v))
    if not -32768 <= n <= 32767:
        raise ToolError(f'{label} value {v} rounds outside int16 range')
    return n


def _mesh_fallback_sphere(points):
    if not points: return (0,0,0),1
    mins=[min(p[k] for p in points) for k in range(3)]; maxs=[max(p[k] for p in points) for k in range(3)]
    c=tuple((mins[k]+maxs[k])/2.0 for k in range(3))
    r=max(math.sqrt(sum((p[k]-c[k])**2 for k in range(3))) for p in points)
    return tuple(_round_i16(x,'sphere center') for x in c),max(1,int(math.ceil(r)))


def _computed_vertex_normals(points, polygons):
    acc=[[0.0,0.0,0.0] for _ in points]
    for p in polygons:
        vs=p['v']
        if len(vs)<3: continue
        try:a=points[vs[0]];b=points[vs[1]];c=points[vs[2]]
        except IndexError: continue
        ux,uy,uz=b[0]-a[0],b[1]-a[1],b[2]-a[2]; vx,vy,vz=c[0]-a[0],c[1]-a[1],c[2]-a[2]
        nx=uy*vz-uz*vy; ny=uz*vx-ux*vz; nz=ux*vy-uy*vx
        mag=math.sqrt(nx*nx+ny*ny+nz*nz)
        if mag==0: continue
        nx/=mag;ny/=mag;nz/=mag
        for vi in vs:
            if 0<=vi<len(acc): acc[vi][0]+=nx;acc[vi][1]+=ny;acc[vi][2]+=nz
    out=[]
    for x,y,z in acc:
        mag=math.sqrt(x*x+y*y+z*z)
        if mag==0: out.append((0,0,0,0)); continue
        s=16300.0/mag; out.append((_round_i16(x*s,'normal'),_round_i16(y*s,'normal'),_round_i16(z*s,'normal'),0))
    return out


def _convert_wad2_mesh_geometry(mesh, name):
    pts=[(_round_i16(x,f'{name} x'),_round_i16(-y,f'{name} y'),_round_i16(z,f'{name} z')) for x,y,z in mesh['positions']]
    if not pts: raise ToolError(f'WAD2 mesh {name} has no vertices')
    if len(pts)>32767: raise ToolError(f'WAD2 mesh {name} has too many vertices ({len(pts)})')
    # WAD2 Lara normals are normally already fixed-point vectors around magnitude 16300.
    normals=[]
    if len(mesh.get('normals',[]))==len(pts):
        for x,y,z in mesh['normals']:
            x=float(x);y=-float(y);z=float(z); mag=math.sqrt(x*x+y*y+z*z)
            if mag<1e-6: normals.append((0,0,0,0)); continue
            s=16300.0/mag
            normals.append((_round_i16(x*s,f'{name} nx'),_round_i16(y*s,f'{name} ny'),_round_i16(z*s,f'{name} nz'),0))
    else:
        normals=_computed_vertex_normals(pts,mesh['polygons'])
    if any(n[:3]==(0,0,0) for n in normals):
        calc=_computed_vertex_normals(pts,mesh['polygons'])
        normals=[calc[i] if n[:3]==(0,0,0) else n for i,n in enumerate(normals)]
    sc=mesh.get('sphere_center'); sr=mesh.get('sphere_radius')
    if sc is not None and sr is not None and math.isfinite(sr) and sr>0:
        center=(_round_i16(sc[0],f'{name} sphere x'),_round_i16(-sc[1],f'{name} sphere y'),_round_i16(sc[2],f'{name} sphere z'))
        radius=max(1,int(math.ceil(sr)))
    else:
        center,radius=_mesh_fallback_sphere(pts)
    quads=[];tris=[]
    for pi,p in enumerate(mesh['polygons']):
        vs=list(p['v'])
        if len(vs) not in (3,4): raise ToolError(f'{name} polygon {pi} is neither triangle nor quad')
        if any(v<0 or v>=len(pts) for v in vs): raise ToolError(f'{name} polygon {pi} has an invalid vertex index')
        rec={'v':vs,'tex':0,'source_polygon':p,'source_polygon_index':pi}
        (quads if len(vs)==4 else tris).append(rec)
    return {'name':name,'center':list(center),'radius':radius,'positions':[(x,y,z,0) for x,y,z in pts],
            'normals':normals,'quads':quads,'triangles':tris,'source_mesh':mesh}


def _serialize_ngage_geometry_record(rec):
    vc=len(rec['positions'])
    blob=bytearray(struct.pack('<3hi h',rec['center'][0],rec['center'][1],rec['center'][2],int(rec['radius']),vc))
    for v in rec['positions']: blob+=struct.pack('<4h',*v)
    for n in rec['normals']: blob+=struct.pack('<4h',*n)
    blob+=struct.pack('<H',len(rec['quads']))
    for f in rec['quads']: blob+=struct.pack('<4HH',*f['v'],int(f.get('tex',0))&0xFFFF)
    blob+=struct.pack('<H',len(rec['triangles']))
    for f in rec['triangles']: blob+=struct.pack('<3HH',*f['v'],int(f.get('tex',0))&0xFFFF)
    if len(blob)&1: raise ToolError('Internal error: N-Gage mesh record has odd byte count')
    return struct.pack('<I',len(blob)//2)+bytes(blob)


def _wad2_geometry_texture_plan(w, records, alpha_threshold=128):
    tex_by_id={t['index']:t for t in w['textures']}
    regions={}; face_info={}; used_textures=set()
    # Only primary records contribute new descriptor definitions; synthetic extras reuse those faces.
    for mi,rec in enumerate(records[:15]):
        for typ in ('quads','triangles'):
            for fi,f in enumerate(rec[typ]):
                p=f['source_polygon']; ti=p['texture']
                if ti not in tex_by_id: raise ToolError(f'WAD2 geometry face refers to missing texture {ti}')
                tex=tex_by_id[ti]; bbox,pts=_wad2_region_for_face(tex,p['uvs']); x0,y0,x1,y1=bbox
                rkey=(ti,x0,y0,x1,y1); regions.setdefault(rkey,(x1-x0+1,y1-y0+1))
                face_info[(mi,typ,fi)]={'region':rkey,'points':pts,'texture':ti}
                used_textures.add(ti)
    if len(used_textures)>MAX_PALETTES:
        raise ToolError(f'Geometry outfit uses {len(used_textures)} textures; N-Gage has {MAX_PALETTES} CLUT groups')
    placement,pack_h=_pack_rectangles(regions)
    texture_group={ti:i for i,ti in enumerate(sorted(used_textures))}
    hist={ti:Counter() for ti in used_textures}
    for rkey in regions:
        ti,x0,y0,x1,y1=rkey; tex=tex_by_id[ti]
        for y in range(y0,y1+1):
            for x in range(x0,x1+1):
                r,g,b,a=wad2.pixel_rgba(tex,x,y)
                if a>=alpha_threshold: hist[ti][rgb_to_psx((r,g,b))]+=1
    palettes=[];rgbp=[]
    for ti in sorted(used_textures):
        reps=weighted_median_cut(hist[ti],15); pal=[0]+reps
        while len(pal)<16: pal.append(reps[0] if reps else rgb_to_psx((1,1,1)))
        palettes.append(pal[:16]);rgbp.append([psx_to_rgb(z) if i else (0,0,0) for i,z in enumerate(pal[:16])])
    while len(palettes)<MAX_PALETTES:
        palettes.append(list(palettes[0]));rgbp.append(list(rgbp[0]))
    idx=[[0]*256 for _ in range(256)];mse=0;opaque=0
    for rkey,(rw,rh) in regions.items():
        ti,x0,y0,x1,y1=rkey;dx,dy=placement[rkey];pg=texture_group[ti];tex=tex_by_id[ti];prgb=rgbp[pg]
        for sy in range(y0,y1+1):
            for sx in range(x0,x1+1):
                r,g,b,a=wad2.pixel_rgba(tex,sx,sy);tx=dx+(sx-x0);ty=dy+(sy-y0)
                if a<alpha_threshold: idx[ty][tx]=0;continue
                c=(r,g,b);k=min(range(1,16),key=lambda z:sum((c[j]-prgb[z][j])**2 for j in range(3)))
                idx[ty][tx]=k;mse+=sum((c[j]-prgb[k][j])**2 for j in range(3));opaque+=1
    words=[]
    for y in range(256):
        for xw in range(64):
            x=xw*4;words.append(idx[y][x]|(idx[y][x+1]<<4)|(idx[y][x+2]<<8)|(idx[y][x+3]<<12))
    for pg in range(MAX_PALETTES):
        for local_y in (177+pg,241+pg):
            base=local_y*64;words[base:base+16]=palettes[pg]
    tpa=struct.pack('<16384H',*words)
    desc_keys=[];key_to_code={};face_code={}
    for fkey,inf in face_info.items():
        ti,x0,y0,x1,y1=inf['region'];dx,dy=placement[inf['region']]
        uv=tuple((dx+(x-x0),dy+(y-y0)) for x,y in inf['points']);pg=texture_group[ti]
        dkey=(len(uv),uv,pg)
        if dkey not in key_to_code:
            if len(desc_keys)>=MAX_DESCRIPTORS: raise ToolError(f'Geometry outfit needs more than {MAX_DESCRIPTORS} texture descriptors')
            key_to_code[dkey]=len(desc_keys);desc_keys.append(dkey)
        face_code[fkey]=key_to_code[dkey]
    return {'tpa':tpa,'idx':idx,'palettes':palettes,'rgbp':rgbp,'regions':regions,'placement':placement,
            'texture_group':texture_group,'face_info':face_info,'face_code':face_code,'desc_keys':desc_keys,
            'key_to_code':key_to_code,'packed_height':pack_h,'used_textures':sorted(used_textures),
            'mse':mse/(max(1,opaque)*3)}


def build_wad2_geometry(wad2_path: Path, reference_lara_path: Path, out: Path, object_id=None, alpha_threshold=128):
    """EXPERIMENTAL: serialize arbitrary 15-mesh WAD2 Lara geometry into N-Gage lara.mesh + matching texture files.

    The generated geometry is intended for the known external lara.mesh replacement path first. Because
    normal levels use the resident Lara topology, this package is NOT safe as a game-wide replacement yet.
    """
    try:w=wad2.load(wad2_path)
    except wad2.WAD2Error as e:raise ToolError(str(e))
    ref=parse_ngage_lara(reference_lara_path);cand=find_wad2_lara_skin(w,ref,object_id,False);mov=cand['moveable']
    primary=[_convert_wad2_mesh_geometry(m,PRIMARY_NAMES[i]) for i,m in enumerate(mov['meshes'])]
    # Synthesize the 11 weapon/holster records from their semantic primary body meshes. This produces
    # geometry-safe records but does not yet add weapon-specific holsters/guns absent from LARA_SKIN.
    records=list(primary)
    variant_rows=[]
    for ei,(obj,source_mi) in enumerate(EXTRA_MAP,start=15):
        src=primary[source_mi]
        clone={'name':f'extra_{obj:02X}_{source_mi:02X}','center':list(src['center']),'radius':src['radius'],
               'positions':list(src['positions']),'normals':list(src['normals']),
               'quads':[dict(f) for f in src['quads']],'triangles':[dict(f) for f in src['triangles']],
               'source_mesh':src['source_mesh'],'synthetic_variant_source_mesh':source_mi}
        records.append(clone);variant_rows.append([ei,clone['name'],source_mi,PRIMARY_NAMES[source_mi],len(clone['positions']),len(clone['quads']),len(clone['triangles'])])
    plan=_wad2_geometry_texture_plan(w,records,alpha_threshold)
    # Extras clone primary face order, so reuse corresponding codes from primary source mesh.
    for ei,(_,source_mi) in enumerate(EXTRA_MAP,start=15):
        src=records[source_mi];dst=records[ei]
        for typ in ('quads','triangles'):
            for fi in range(len(dst[typ])):
                plan['face_code'][(ei,typ,fi)]=plan['face_code'][(source_mi,typ,fi)]
    def safe_unused(bank):return make_desc([(0,0)]*4,0,bank)
    A=[safe_unused('A') for _ in range(MAX_DESCRIPTORS)];B=[safe_unused('B') for _ in range(MAX_DESCRIPTORS)]
    for dkey,code in plan['key_to_code'].items():
        n,uv,pg=dkey;j=100-code;A[j]=make_desc(list(uv),pg,'A');B[j]=make_desc(list(uv),pg,'B')
    # Build matching retexture stream and set redundant face texture values to zero in lara.mesh.
    stream=bytearray();patch_rows=[]
    for mi,r in enumerate(records):
        for typ in ('quads','triangles'):
            for fi,f in enumerate(r[typ]):
                code=plan['face_code'][(mi,typ,fi)];vs=f['v']
                stream+=struct.pack('<'+'H'*len(vs),*vs)+struct.pack('<H',code)
                patch_rows.append([mi,r['name'],'quad' if typ=='quads' else 'triangle',fi,' '.join(map(str,vs)),code,
                                   getattr(r,'synthetic_variant_source_mesh',None) if False else r.get('synthetic_variant_source_mesh','')])
    rt=b''.join(A)+b''.join(B)+bytes(stream)
    lara=b''.join(_serialize_ngage_geometry_record(r) for r in records)
    out.mkdir(parents=True,exist_ok=True);(out/'lara.mesh').write_bytes(lara);(out/'new_tpage.tpa').write_bytes(plan['tpa']);(out/'retexture.dat').write_bytes(rt)
    # Round-trip validate generated mesh and retexture stream.
    parsed=parse_ngage_lara(out/'lara.mesh')
    if len(parsed)!=26:raise ToolError('Generated lara.mesh did not parse back to 26 records')
    p=3232;face_count=0
    for r in parsed:
        for f in r['quads']+r['triangles']:
            need=len(f['v'])*2+2
            if p+need>len(rt):raise ToolError('Generated geometry retexture stream is truncated')
            p+=need;face_count+=1
    if p!=len(rt):raise ToolError(f'Generated geometry retexture stream ended at {p}, file size is {len(rt)}')
    # Reports.
    with (out/'patch_summary.csv').open('w',newline='') as f:
        wr=csv.writer(f);wr.writerow(['mesh_index','mesh_name','face_type','face_index','vertices','local_code','synthetic_variant_source_mesh']);wr.writerows(patch_rows)
    with (out/'variant_map.csv').open('w',newline='') as f:
        wr=csv.writer(f);wr.writerow(['record','name','source_primary_mesh','source_name','vertices','quads','triangles']);wr.writerows(variant_rows)
    with (out/'atlas_layout.csv').open('w',newline='') as f:
        wr=csv.writer(f);wr.writerow(['source_texture','src_x0','src_y0','src_x1','src_y1','width','height','dst_x','dst_y','palette_group'])
        for rkey,(rw,rh) in sorted(plan['regions'].items()):
            ti,x0,y0,x1,y1=rkey;dx,dy=plan['placement'][rkey];wr.writerow([ti,x0,y0,x1,y1,rw,rh,dx,dy,plan['texture_group'][ti]])
    def preview_pixel(x,y):
        k=plan['idx'][y][x]
        if k==0:return TRANSPARENT_DEFAULT
        pg=0
        for rkey,(rw,rh) in plan['regions'].items():
            dx,dy=plan['placement'][rkey]
            if dx<=x<dx+rw and dy<=y<dy+rh:pg=plan['texture_group'][rkey[0]];break
        return plan['rgbp'][pg][k]
    write_png_rgb(out/'atlas_preview.png',256,256,preview_pixel);write_png_rgb(out/'atlas_preview_4x.png',256,256,preview_pixel,4)
    mesh_rows=[]
    for i,r in enumerate(records):
        mesh_rows.append({'index':i,'name':r['name'],'vertices':len(r['positions']),'quads':len(r['quads']),'triangles':len(r['triangles']),
                          'center':r['center'],'radius':r['radius'],'synthetic_variant_source_mesh':r.get('synthetic_variant_source_mesh')})
    primary_faces=sum(len(r['quads'])+len(r['triangles']) for r in records[:15]);extra_faces=face_count-primary_faces
    manifest={'tool':'TR N-Gage Outfit Tool','version':VERSION,'mode':'wad2_geometry_serializer_experimental',
              'source_wad2':str(wad2_path),'source_wad2_sha256':sha256(wad2_path.read_bytes()),'selected_object_id':cand['object_id'],
              'source_grade':cand['grade'],'primary_meshes':15,'records':26,'primary_faces':primary_faces,'synthetic_variant_faces':extra_faces,
              'total_faces':face_count,'descriptor_count':len(plan['desc_keys']),'used_source_textures':plan['used_textures'],
              'unique_packed_regions':len(plan['regions']),'packed_height':plan['packed_height'],'quantization_mse_rgb_channel':plan['mse'],
              'lara_mesh_size':len(lara),'retexture_size':len(rt),'tpa_size':len(plan['tpa']),
              'sha256_lara_mesh':sha256(lara),'sha256_retexture':sha256(rt),'sha256_tpa':sha256(plan['tpa']),
              'normal_strategy':'WAD2 vertex normals normalized to magnitude 16300; computed fallback if missing',
              'bounds_strategy':'WAD2 W2MeshSphere when available, otherwise computed bbox sphere',
              'variant_strategy':'11 weapon/holster records cloned from corresponding primary body meshes; weapon-specific geometry not yet authored',
              'runtime_status':'SPECIAL-PATH LAB ONLY. Do not install this retexture.dat for ordinary levels; its face stream follows the custom topology.',
              'meshes':mesh_rows}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'EXPERIMENTAL-NOTICE.txt').write_text(
        'TR N-Gage Outfit Tool v0.4 geometry serializer - EXPERIMENTAL\n\n'
        'This build changes Lara topology. The generated retexture.dat follows the generated lara.mesh face stream.\n'
        'The stock game only uses external lara.mesh on the previously identified special replacement path.\n'
        'DO NOT leave this retexture.dat installed while loading ordinary levels: those levels use the resident Lara\n'
        'topology and a different face count, so the stream is not game-wide safe yet.\n\n'
        'The next project step is a small NAX runtime patch that activates the external custom geometry + matching\n'
        'patch stream consistently in normal levels. Until then this output is a serializer/special-path laboratory.\n')
    return manifest


def convert(wad_path: Path, lara_path: Path, out: Path, forced_start=None,
            transparent=TRANSPARENT_DEFAULT, map_weapon_variants=False):
    out.mkdir(parents=True,exist_ok=True)
    wad=parse_classic_wad(wad_path)
    ng=parse_ngage_lara(lara_path)
    cand=find_lara_skin(wad,ng,forced_start)
    src=cand['meshes']

    # Match source primary faces to N-Gage primary faces.
    match_rows=[]; match_for_ng={}; used_samples=set()
    for mi in range(15):
        by=defaultdict(list)
        for bi,bf in enumerate(src[mi]['faces']):
            by[(len(bf['v']),canon(bf['v']))].append((bi,bf))
        ngfaces=ng[mi]['quads']+ng[mi]['triangles']
        for ni,nf in enumerate(ngfaces):
            c=by.get((len(nf['v']),canon(nf['v'])),[])
            if not c:
                match_rows.append([mi,PRIMARY_NAMES[mi],ni,len(nf['v']),'','','',False])
                continue
            bi,bf=c[0]
            sample,rel=decode_classic_texture(bf,wad['samples'])
            bv=tuple(bf['v']); nv=tuple(nf['v']); n=len(bv)
            cyclic=any(nv==bv[i:]+bv[:i] for i in range(n))
            if not cyclic:
                # Canonically same but reversed winding. the classic-WAD converter refuses this match because changing
                # winding could alter culling and descriptor orientation.
                match_rows.append([mi,PRIMARY_NAMES[mi],ni,len(nf['v']),'','','',False])
                continue
            match_for_ng[(mi,ni)]={'source_mesh':mi,'source_face_index':bi,'face':bf,'sample':sample,'rel_uv':rel}
            used_samples.add(sample)
            match_rows.append([mi,PRIMARY_NAMES[mi],ni,len(nf['v']),bi,f'0x{bf["texture_word"]:04X}',sample,True])

    # Experimental but useful: N-Gage extra weapon records name the corresponding Lara mesh index
    # in EXTRA_MAP. Reuse source textures on faces whose topology is identical.
    weapon_matches=0
    if map_weapon_variants:
        for ngi,(obj,source_mi) in enumerate(EXTRA_MAP,start=15):
            by=defaultdict(list)
            for bi,bf in enumerate(src[source_mi]['faces']):
                by[(len(bf['v']),canon(bf['v']))].append((bi,bf))
            for ni,nf in enumerate(ng[ngi]['quads']+ng[ngi]['triangles']):
                c=by.get((len(nf['v']),canon(nf['v'])),[])
                if not c: continue
                bi,bf=c[0]
                bv=tuple(bf['v']); nv=tuple(nf['v']); n=len(bv)
                if not any(nv==bv[i:]+bv[:i] for i in range(n)): continue
                sample,rel=decode_classic_texture(bf,wad['samples'])
                match_for_ng[(ngi,ni)]={'source_mesh':source_mi,'source_face_index':bi,'face':bf,'sample':sample,'rel_uv':rel}
                used_samples.add(sample); weapon_matches += 1

    if not match_for_ng:
        raise ToolError('No compatible Lara faces could be mapped')

    # Pack source sample rectangles into the top 176 rows.
    rects=[]
    for si in used_samples:
        sm=wad['samples'][si]; rects.append((sm['h'],sm['w'],si))
    rects.sort(reverse=True)
    shelves=[]; placement={}
    for h,w,si in rects:
        candidates=[]
        for k,sh in enumerate(shelves):
            if h<=sh['h'] and sh['x']+w<=256:
                candidates.append((sh['h']-h,sh['x'],k))
        if candidates:
            _,_,k=min(candidates); sh=shelves[k]; x=sh['x']; y=sh['y']; sh['x']+=w
        else:
            y=sum(sh['h'] for sh in shelves)
            sh={'y':y,'h':h,'x':w}; shelves.append(sh); x=0
        placement[si]=(x,y)
    pack_h=sum(sh['h'] for sh in shelves)
    if pack_h>PIXEL_REGION_MAX_Y:
        raise ToolError(f'Used texture rectangles need {pack_h} atlas rows; safe pixel region is {PIXEL_REGION_MAX_Y}.')

    # Cache sample pixels and build palette groups.
    sample_pixels={si:crop_pixels(wad,si) for si in used_samples}
    color_sets={}; color_counts={}
    for si in used_samples:
        cnt=Counter(c for row in sample_pixels[si] for c in row)
        cnt.pop(transparent,None)
        color_counts[si]=cnt; color_sets[si]=set(cnt)
    groups=[]
    for si in sorted(used_samples,key=lambda i:len(color_sets[i]),reverse=True):
        if len(color_sets[si])>15:
            groups.append({'samples':[si],'colors':set(color_sets[si]),'needs_quant':True})
            continue
        best=None
        for gi,G in enumerate(groups):
            if G.get('needs_quant'): continue
            u=G['colors']|color_sets[si]
            if len(u)<=15:
                score=(len(G['colors']&color_sets[si]),-len(u))
                if best is None or score>best[0]: best=(score,gi,u)
        if best:
            _,gi,u=best; groups[gi]['samples'].append(si); groups[gi]['colors']=u
        else:
            groups.append({'samples':[si],'colors':set(color_sets[si]),'needs_quant':False})
    if len(groups)>MAX_PALETTES:
        raise ToolError(f'This outfit requires {len(groups)} independent palette groups; N-Gage format has {MAX_PALETTES}. v0.2 does not yet merge palette groups lossily in WAD-conversion mode.')
    sample_group={si:gi for gi,G in enumerate(groups) for si in G['samples']}

    palettes=[]; rgb_palettes=[]
    for G in groups:
        freq=Counter()
        for si in G['samples']: freq.update(color_counts[si])
        qfreq=Counter()
        for c,n in freq.items(): qfreq[rgb_to_psx(c)]+=n
        words=[w for w,_ in qfreq.most_common(15)]
        if not words: words=[rgb_to_psx((1,1,1))]
        pal=[0]+words
        while len(pal)<16: pal.append(words[0])
        palettes.append(pal[:16])
        rgb_palettes.append([psx_to_rgb(w) if i else (0,0,0) for i,w in enumerate(pal[:16])])
    while len(palettes)<MAX_PALETTES:
        palettes.append(list(palettes[0])); rgb_palettes.append(list(rgb_palettes[0]))

    def nearest_index(gi,c):
        if c==transparent: return 0
        pal=rgb_palettes[gi]
        return min(range(1,16), key=lambda k: sum((c[j]-pal[k][j])**2 for j in range(3)))

    idx=[[0]*256 for _ in range(256)]
    quant_error=0; quant_pixels=0
    for si in sorted(used_samples):
        x0,y0=placement[si]; pix=sample_pixels[si]; gi=sample_group[si]
        for y,row in enumerate(pix):
            for x,c in enumerate(row):
                k=nearest_index(gi,c); idx[y0+y][x0+x]=k
                if c!=transparent:
                    pc=rgb_palettes[gi][k]
                    quant_error += sum((c[j]-pc[j])**2 for j in range(3)); quant_pixels += 1

    words=[]
    for y in range(256):
        for xw in range(64):
            x=xw*4
            words.append(idx[y][x] | (idx[y][x+1]<<4) | (idx[y][x+2]<<8) | (idx[y][x+3]<<12))
    # WAD conversion duplicates the same custom palettes into both banks. This is safe, but does not attempt
    # to recreate the game's alternate/underwater tint.
    for gi in range(MAX_PALETTES):
        for local_y in (177+gi,241+gi):
            base=local_y*64
            words[base:base+16]=palettes[gi]
    tpa=struct.pack('<'+'H'*len(words),*words)
    if len(tpa)!=32768: raise AssertionError(len(tpa))

    # Determine reusable descriptors.
    desc_keys=[]; key_to_code={}; face_code={}
    for mi,r in enumerate(ng):
        for ni,nf in enumerate(r['quads']+r['triangles']):
            m=match_for_ng.get((mi,ni))
            if not m: continue
            si=m['sample']; x0,y0=placement[si]
            uv=tuple((x0+du,y0+dv) for du,dv in m['rel_uv'])
            gi=sample_group[si]
            key=(len(uv),uv,gi)
            if key not in key_to_code:
                code=len(desc_keys)
                if code>=MAX_DESCRIPTORS:
                    raise ToolError(f'Outfit needs more than {MAX_DESCRIPTORS} unique N-Gage texture descriptors')
                key_to_code[key]=code; desc_keys.append(key)
            face_code[(mi,ni)]=key_to_code[key]

    def safe_unused(bank): return make_desc([(0,0),(0,0),(0,0),(0,0)],0,bank)
    A=[safe_unused('A') for _ in range(MAX_DESCRIPTORS)]
    Btab=[safe_unused('B') for _ in range(MAX_DESCRIPTORS)]
    for key,code in key_to_code.items():
        n,uv,gi=key; j=100-code
        A[j]=make_desc(list(uv),gi,'A'); Btab[j]=make_desc(list(uv),gi,'B')

    stream=bytearray(); patch_rows=[]
    for mi,r in enumerate(ng):
        for ni,f in enumerate(r['quads']+r['triangles']):
            n=len(f['v']); m=match_for_ng.get((mi,ni))
            if m:
                verts=m['face']['v']; code=face_code[(mi,ni)]; action='custom'
            else:
                verts=f['v']; code=0xFFFF; action='classic_fallback'
            stream += struct.pack('<'+'H'*n,*verts)+struct.pack('<H',code)
            patch_rows.append([mi,r['name'],'quad' if n==4 else 'triangle',ni,' '.join(map(str,verts)),code,action])
    rt=b''.join(A)+b''.join(Btab)+bytes(stream)
    if len(rt)!=9006:
        raise ToolError(f'Generated retexture.dat has unexpected size {len(rt)} (expected 9006)')

    (out/'new_tpage.tpa').write_bytes(tpa)
    (out/'retexture.dat').write_bytes(rt)

    # Reports
    with (out/'face_mapping.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['mesh_index','mesh_name','ngage_face_index','vertices','source_face_index','source_texture_word','source_sample','matched']); w.writerows(match_rows)
    with (out/'patch_summary.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['mesh_index','mesh_name','face_type','face_index','replacement_vertices','local_code','action']); w.writerows(patch_rows)
    with (out/'atlas_layout.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['sample','src_page','src_x','src_y','width','height','dst_x','dst_y','palette_group'])
        for si in sorted(used_samples):
            sm=wad['samples'][si]; x0,y0=placement[si]
            w.writerow([si,sm['page'],sm['x'],sm['y'],sm['w'],sm['h'],x0,y0,sample_group[si]])
    with (out/'palette_groups.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['group','samples','opaque_palette_words'])
        for gi,G in enumerate(groups): w.writerow([gi,' '.join(map(str,sorted(G['samples']))),' '.join(f'{x:04X}' for x in palettes[gi][1:])])

    def preview_pixel(x,y):
        k=idx[y][x]
        if k==0: return transparent
        # Identify palette by containing placed sample. Background falls back to group 0.
        gi=0
        for si,(x0,y0) in placement.items():
            sm=wad['samples'][si]
            if x0<=x<x0+sm['w'] and y0<=y<y0+sm['h']:
                gi=sample_group[si]; break
        return rgb_palettes[gi][k]
    write_bmp24(out/'atlas_preview.bmp',256,256,preview_pixel,1)
    write_bmp24(out/'atlas_preview_4x.bmp',256,256,preview_pixel,4)

    primary_total=sum(len(ng[i]['quads'])+len(ng[i]['triangles']) for i in range(15))
    primary_mapped=sum(1 for k in match_for_ng if k[0]<15)
    extra_total=sum(len(ng[i]['quads'])+len(ng[i]['triangles']) for i in range(15,26))
    extra_mapped=sum(1 for k in match_for_ng if k[0]>=15)
    mse=quant_error/(max(1,quant_pixels)*3)
    summary={
        'tool':'TR N-Gage Outfit Tool','version':VERSION,
        'source_wad':str(wad_path),'source_wad_sha256':sha256(wad_path.read_bytes()),
        'lara_mesh':str(lara_path),'lara_mesh_sha256':sha256(lara_path.read_bytes()),
        'detected_lara_mesh_pointer_start':cand['start'],
        'source_vertex_count_matches':cand['vertex_count_matches'],
        'source_topology_matches':cand['topology_matches'],
        'source_topology_total':cand['topology_total'],
        'used_source_samples':len(used_samples),'palette_groups_used':len(groups),
        'packed_height':pack_h,'descriptor_count':len(desc_keys),
        'primary_ngage_faces':primary_total,'mapped_primary_faces':primary_mapped,
        'primary_fallback_faces':primary_total-primary_mapped,
        'weapon_extra_faces':extra_total,'mapped_weapon_extra_faces':extra_mapped,
        'weapon_extra_fallback_faces':extra_total-extra_mapped,
        'map_weapon_variants':bool(map_weapon_variants),
        'retexture_size':len(rt),'tpa_size':len(tpa),
        'quantization_mse_rgb_channel':mse,
        'sha256_retexture':sha256(rt),'sha256_tpa':sha256(tpa),
        'alternate_palette_bank':'duplicate of normal bank (classic-WAD mode)',
        'hardware_notes':'Normal-level classic-fallback behavior proven. Special level IDs 16/17/19 use lara.mesh fallback semantics and are not a current classic-WAD target.'
    }
    (out/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    (out/'INSTALL.txt').write_text(
        'TR N-Gage Outfit Tool output\n\n'
        'BACK UP YOUR ORIGINAL FILES FIRST.\n\n'
        'Copy these two generated files to:\n'
        'E:\\System\\Apps\\tombraider\\data\\deldata\\\n\n'
        '  new_tpage.tpa\n'
        '  retexture.dat\n\n'
        'Leave lara.mesh unchanged for current texture-only/classic-WAD conversions.\n'
        'For first testing, use an early/normal level and test Lara unarmed first.\n'
    )
    return summary


# ---------- Inspectors ----------
def inspect_lara(path: Path):
    recs=parse_ngage_lara(path)
    d=[]
    for r in recs:
        d.append({'index':r['index'],'name':r['name'],'vertices':abs(r['vertex_count']),
                  'quads':len(r['quads']),'triangles':len(r['triangles']),
                  'texture_indices':sorted({f['tex'] for f in r['quads']+r['triangles']})})
    return {'file':str(path),'size':path.stat().st_size,'sha256':sha256(path.read_bytes()),'records':d}


def inspect_retexture(path: Path, lara_path: Path|None=None):
    b=path.read_bytes()
    if len(b)<3232: raise ToolError('retexture.dat is shorter than the two 101x16 descriptor tables')
    result={'file':str(path),'size':len(b),'sha256':sha256(b),
            'descriptor_table_A_bytes':1616,'descriptor_table_B_bytes':1616,
            'patch_stream_bytes':len(b)-3232}
    if lara_path:
        recs=parse_ngage_lara(lara_path); p=3232; codes=[]; faces=0
        for r in recs:
            for f in r['quads']+r['triangles']:
                n=len(f['v']); need=n*2+2
                if p+need>len(b): raise ToolError(f'retexture.dat patch stream truncates at face {faces}')
                vals=struct.unpack_from('<'+'H'*(n+1),b,p); p+=need
                codes.append(vals[-1]); faces+=1
        result.update({'faces':faces,'parsed_end':p,'exact_eof':p==len(b),
                       'custom_codes_0_100':sum(0<=c<=100 for c in codes),
                       'fallback_ffff':sum(c==0xFFFF for c in codes),
                       'other_codes':sum(c>100 and c!=0xFFFF for c in codes),
                       'used_codes':sorted(set(c for c in codes if c<=100))})
    return result


def inspect_tpa(path: Path):
    b=path.read_bytes()
    if len(b)!=32768: raise ToolError(f'Expected a 32768-byte new_tpage.tpa, got {len(b)}')
    words=struct.unpack('<16384H',b)
    cluts={}
    for bank,ys in [('B',range(177,192)),('A',range(241,256))]:
        cluts[bank]=[[f'{w:04X}' for w in words[y*64:y*64+16]] for y in ys]
    return {'file':str(path),'size':len(b),'sha256':sha256(b),'format':'64x256 16-bit VRAM words = 256x256 4-bpp texture page','cluts':cluts}



# ---------- Hardware-confirmed diagnostic examples ----------
# These presets are deliberately tied to the stock AoD outfit files used during
# reverse engineering. They are educational/diagnostic examples, not generic
# outfit transforms. The exact hashes prevent accidental application to a
# different custom retexture layout where local code 18 or the face sets could
# mean something else.
STOCK_AOD_TPA_SHA256 = '0c0f7a8fb1ccd43d45a088b4c589e6135b396823a5fe8ef8ffada962fe829daa'
STOCK_AOD_RETEXTURE_SHA256 = '28cf4e94bf067d6d72122d42b1d14d11963d95b7f674a422dfa93a54d44c21bf'
STOCK_LARA_MESH_SHA256 = '5efbf356810f0e26cfe8fc0f53341dd865314672f2abc2047a4d00f13094b2db'
DIAG_ARM_CODE = 18
DIAG_TORSO_TOP_CODES = {1,35,36,37,39,40,41,42,43,44,45,46}
DIAG_PANTS_MESHES = {1,2,4,5}
DIAG_PELVIS_BELT_FACES = {6,7,9,16,17,22,23}
DIAGNOSTIC_PRESETS = {
    'arm-body-contrast': {
        'title':'Arm/Body Contrast',
        'description':'Map torso/top and thigh/calf pants faces to Lara arm/skin descriptor 18 while leaving the whole pelvis mesh untouched.',
    },
    'pants-belt-isolation': {
        'title':'Pants + Belt Isolation',
        'description':'Follow-up: also remap the main pelvis/shorts faces to arm/skin descriptor 18 while preserving the upper waistband/belt faces.',
    },
}


def _require_stock_aod_examples(tpa_path: Path, retexture_path: Path, lara_path: Path):
    tb=tpa_path.read_bytes(); rb=retexture_path.read_bytes(); lb=lara_path.read_bytes()
    got={'new_tpage.tpa':sha256(tb),'retexture.dat':sha256(rb),'lara.mesh':sha256(lb)}
    exp={'new_tpage.tpa':STOCK_AOD_TPA_SHA256,'retexture.dat':STOCK_AOD_RETEXTURE_SHA256,'lara.mesh':STOCK_LARA_MESH_SHA256}
    bad=[f'{k}: expected {exp[k]}, got {got[k]}' for k in exp if got[k]!=exp[k]]
    if bad:
        raise ToolError('Diagnostic examples are defined for the stock AoD reference outfit only. Hash mismatch:\n  '+'\n  '.join(bad))
    return tb,rb,lb


def make_diagnostic_example(preset: str, tpa_path: Path, retexture_path: Path, lara_path: Path, out: Path):
    if preset not in DIAGNOSTIC_PRESETS:
        raise ToolError(f'Unknown diagnostic preset {preset!r}')
    tpa,rt,_=_require_stock_aod_examples(tpa_path,retexture_path,lara_path)
    recs=parse_ngage_lara(lara_path)
    raw=bytearray(rt)
    if len(raw)!=9006:
        raise ToolError(f'Expected 9006-byte stock retexture.dat, got {len(raw)}')
    p=3232; changed=[]; preserved=[]
    for mi,r in enumerate(recs):
        for fi,f in enumerate(r['quads']+r['triangles']):
            n=len(f['v']); code_off=p+n*2
            old=struct.unpack_from('<H',raw,code_off)[0]
            new=old; reason='unchanged'
            if preset=='pants-belt-isolation' and mi==0:
                if fi in DIAG_PELVIS_BELT_FACES:
                    reason='pelvis_belt_upper_band_preserved'; preserved.append((mi,r['name'],fi,old,reason))
                else:
                    new=DIAG_ARM_CODE; reason='pelvis_pants_to_arm_texture'
            elif mi in DIAG_PANTS_MESHES:
                new=DIAG_ARM_CODE; reason='pants_to_arm_texture'
            elif mi==7 and old in DIAG_TORSO_TOP_CODES:
                new=DIAG_ARM_CODE; reason='top_to_arm_texture'
            if new!=old:
                struct.pack_into('<H',raw,code_off,new)
                changed.append((mi,r['name'],fi,'quad' if n==4 else 'triangle',old,new,reason))
            p += n*2+2
    if p!=len(raw):
        raise ToolError(f'Patch walk ended at {p}, retexture size is {len(raw)}')
    mod=bytes(raw)
    out.mkdir(parents=True,exist_ok=True); install=out/'INSTALL'; install.mkdir(exist_ok=True)
    (out/'new_tpage.tpa').write_bytes(tpa); (out/'retexture.dat').write_bytes(mod)
    (install/'new_tpage.tpa').write_bytes(tpa); (install/'retexture.dat').write_bytes(mod)
    with (out/'changed_faces.csv').open('w',newline='') as f:
        w=csv.writer(f); w.writerow(['mesh_index','mesh_name','face_index','face_type','old_code','new_code','reason']); w.writerows(changed)
    if preserved:
        with (out/'preserved_pelvis_belt_faces.csv').open('w',newline='') as f:
            w=csv.writer(f); w.writerow(['mesh_index','mesh_name','face_index','texture_code','reason']); w.writerows(preserved)
    info=DIAGNOSTIC_PRESETS[preset]
    summary={
        'tool_version':VERSION,'preset':preset,'title':info['title'],'description':info['description'],
        'stock_tpa_sha256':sha256(tpa),'stock_retexture_sha256':sha256(rt),'lara_mesh_sha256':sha256(lara_path.read_bytes()),
        'generated_tpa_sha256':sha256(tpa),'generated_retexture_sha256':sha256(mod),
        'new_tpage_is_unchanged':mod is not None and sha256(tpa)==STOCK_AOD_TPA_SHA256,
        'changed_face_records':len(changed),'arm_texture_local_code':DIAG_ARM_CODE,
        'pelvis_belt_faces_preserved':sorted(DIAG_PELVIS_BELT_FACES) if preset=='pants-belt-isolation' else [],
        'generated_retexture_size':len(mod),'generated_tpa_size':len(tpa),
    }
    (out/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    install_note=(
        f"TR N-Gage Outfit Tool v{VERSION} — {info['title']} diagnostic\n\n"
        "BACK UP YOUR ORIGINAL FILES FIRST.\n\n"
        "Copy INSTALL\\new_tpage.tpa and INSTALL\\retexture.dat to:\n"
        "E:\\System\\Apps\\tombraider\\data\\deldata\\\n\n"
        "Leave lara.mesh unchanged. Test an early/normal level first.\n\n"
        + info['description'] + '\n'
    )
    (out/'INSTALL.txt').write_text(install_note)
    return summary

def parse_rgb_triplet(s):
    try:
        p=tuple(int(x.strip()) for x in s.split(','))
        if len(p)!=3 or any(x<0 or x>255 for x in p): raise ValueError
        return p
    except ValueError:
        raise argparse.ArgumentTypeError('RGB must be R,G,B with values 0..255')


def main(argv=None):
    ap=argparse.ArgumentParser(prog='tr_ngage_outfit.py',description=f'TR N-Gage Outfit Tool v{VERSION}')
    ap.add_argument('--version',action='version',version=f'%(prog)s {VERSION}')
    sub=ap.add_subparsers(dest='cmd',required=True)

    c=sub.add_parser('convert-wad',help='Convert a topology-compatible classic WAD (id 129) to N-Gage outfit files')
    c.add_argument('wad',type=Path)
    c.add_argument('--lara-mesh',required=True,type=Path,help='Original N-Gage deldata/lara.mesh used as topology reference')
    c.add_argument('-o','--out',required=True,type=Path)
    c.add_argument('--mesh-start',type=int,default=None,help='Override auto-detected first Lara mesh pointer')
    c.add_argument('--transparent',type=parse_rgb_triplet,default=TRANSPARENT_DEFAULT,help='Source transparent RGB key, default 255,0,255')
    c.add_argument('--map-weapon-variants',action='store_true',help='EXPERIMENTAL: map topology-compatible weapon/holster variant faces too')

    a=sub.add_parser('analyze-wad',help='Analyze compatibility without writing outfit files')
    a.add_argument('wad',type=Path); a.add_argument('--lara-mesh',required=True,type=Path); a.add_argument('--mesh-start',type=int)

    w2a=sub.add_parser('analyze-wad2',help='Analyze a Tomb Editor WAD2 Lara candidate and classify texture-vs-geometry compatibility')
    w2a.add_argument('wad2',type=Path); w2a.add_argument('--lara-mesh',required=True,type=Path); w2a.add_argument('--object-id',type=int)

    w2c=sub.add_parser('convert-wad2',help='Convert a topology-compatible WAD2 LARA_SKIN to N-Gage TPA + retexture.dat')
    w2c.add_argument('wad2',type=Path); w2c.add_argument('--lara-mesh',required=True,type=Path); w2c.add_argument('-o','--out',required=True,type=Path)
    w2c.add_argument('--object-id',type=int,help='Override auto-detected 15-mesh Lara object ID')
    w2c.add_argument('--alpha-threshold',type=int,default=128,help='WAD2 alpha below this value becomes transparent (0..255, default 128)')
    w2c.add_argument('--fallback-mode',choices=['auto','classic','uniform'],default='auto',help='auto=complete unmatched faces only for fully-opaque single-color skins; classic=leave unmatched faces Classic; uniform=force completion and require a uniform source')

    w2e=sub.add_parser('export-wad2-model',help='Export a WAD2 Lara candidate as OBJ parts + source textures for geometry development')
    w2e.add_argument('wad2',type=Path); w2e.add_argument('--lara-mesh',required=True,type=Path); w2e.add_argument('-o','--out',required=True,type=Path)
    w2e.add_argument('--object-id',type=int,help='Override auto-detected 15-mesh Lara object ID')

    w2g=sub.add_parser('build-wad2-geometry',help='EXPERIMENTAL: serialize arbitrary WAD2 LARA_SKIN geometry into lara.mesh + matching TPA/retexture files')
    w2g.add_argument('wad2',type=Path); w2g.add_argument('--lara-mesh',required=True,type=Path,help='Original N-Gage lara.mesh used for semantic record/reference layout')
    w2g.add_argument('-o','--out',required=True,type=Path); w2g.add_argument('--object-id',type=int,help='Override auto-detected 15-mesh Lara object ID')
    w2g.add_argument('--alpha-threshold',type=int,default=128,help='WAD2 alpha below this value becomes transparent (0..255, default 128)')

    il=sub.add_parser('inspect-lara',help='Inspect N-Gage lara.mesh')
    il.add_argument('lara_mesh',type=Path)
    ir=sub.add_parser('inspect-retexture',help='Inspect N-Gage retexture.dat')
    ir.add_argument('retexture',type=Path); ir.add_argument('--lara-mesh',type=Path)
    it=sub.add_parser('inspect-tpa',help='Inspect N-Gage new_tpage.tpa')
    it.add_argument('tpa',type=Path)

    ex=sub.add_parser('export-textures',help='Export an existing N-Gage outfit to an editable PNG/BMP workspace (no WAD needed)')
    ex.add_argument('tpa',type=Path,help='Existing new_tpage.tpa')
    ex.add_argument('--retexture',required=True,type=Path,help='Matching retexture.dat')
    ex.add_argument('--lara-mesh',required=True,type=Path,help='Matching/original lara.mesh used to identify triangle/quad descriptor usage')
    ex.add_argument('-o','--out',required=True,type=Path,help='Workspace output folder')
    ex.add_argument('--transparent',type=parse_rgb_triplet,default=TRANSPARENT_DEFAULT,help='Editable transparent RGB key, default 255,0,255')

    im=sub.add_parser('import-textures',help='Import an edited texture workspace and rebuild N-Gage outfit files')
    im.add_argument('workspace',type=Path,help='Folder previously made by export-textures')
    im.add_argument('--image',type=Path,default=None,help='Edited 256x256 PNG/BMP; default workspace/texture_edit.png')
    im.add_argument('-o','--out',required=True,type=Path)
    im.add_argument('--alternate-mode',choices=['duplicate','preserve'],default='duplicate',help='duplicate=copy edited normal palettes into alternate bank (recommended); preserve=leave old alternate CLUT words')

    dx=sub.add_parser('make-example',help='Generate one of the documented stock-AoD diagnostic example file sets')
    dx.add_argument('preset',choices=sorted(DIAGNOSTIC_PRESETS))
    dx.add_argument('tpa',type=Path,help='Stock/reference AoD new_tpage.tpa')
    dx.add_argument('--retexture',required=True,type=Path,help='Stock/reference AoD retexture.dat')
    dx.add_argument('--lara-mesh',required=True,type=Path,help='Reference lara.mesh')
    dx.add_argument('-o','--out',required=True,type=Path)

    args=ap.parse_args(argv)
    try:
        if args.cmd=='convert-wad':
            s=convert(args.wad,args.lara_mesh,args.out,args.mesh_start,args.transparent,args.map_weapon_variants)
            print(json.dumps(s,indent=2))
            print(f'\nSUCCESS: output written to {args.out}')
        elif args.cmd=='analyze-wad':
            wad=parse_classic_wad(args.wad); ng=parse_ngage_lara(args.lara_mesh); c=find_lara_skin(wad,ng,args.mesh_start)
            print(json.dumps({
                'wad':str(args.wad),'file_id':wad['file_id'],'texture_samples':len(wad['samples']),
                'texture_pages':wad['texture_page_count'],'mesh_pointers':len(wad['ptrs']),
                'detected_lara_mesh_pointer_start':c['start'],
                'vertex_count_matches':c['vertex_count_matches'],
                'topology_matches':c['topology_matches'],'topology_total':c['topology_total'],
                'topology_coverage':c['topology_matches']/max(1,c['topology_total'])
            },indent=2))
        elif args.cmd=='analyze-wad2':
            print(json.dumps(analyze_wad2_file(args.wad2,args.lara_mesh,args.object_id),indent=2))
        elif args.cmd=='convert-wad2':
            if not 0<=args.alpha_threshold<=255: raise ToolError('--alpha-threshold must be 0..255')
            s=convert_wad2(args.wad2,args.lara_mesh,args.out,args.object_id,args.alpha_threshold,args.fallback_mode)
            print(json.dumps(s,indent=2)); print(f'\nSUCCESS: WAD2 outfit files written to {args.out}')
        elif args.cmd=='export-wad2-model':
            s=export_wad2_model(args.wad2,args.lara_mesh,args.out,args.object_id)
            print(json.dumps(s,indent=2)); print(f'\nSUCCESS: WAD2 model lab export written to {args.out}')
        elif args.cmd=='build-wad2-geometry':
            if not 0<=args.alpha_threshold<=255: raise ToolError('--alpha-threshold must be 0..255')
            s=build_wad2_geometry(args.wad2,args.lara_mesh,args.out,args.object_id,args.alpha_threshold)
            print(json.dumps(s,indent=2)); print(f'\nSUCCESS: experimental WAD2 geometry bundle written to {args.out}')
        elif args.cmd=='inspect-lara': print(json.dumps(inspect_lara(args.lara_mesh),indent=2))
        elif args.cmd=='inspect-retexture': print(json.dumps(inspect_retexture(args.retexture,args.lara_mesh),indent=2))
        elif args.cmd=='inspect-tpa': print(json.dumps(inspect_tpa(args.tpa),indent=2))
        elif args.cmd=='export-textures':
            s=export_texture_workspace(args.tpa,args.retexture,args.lara_mesh,args.out,args.transparent)
            print(json.dumps(s,indent=2)); print(f'\nSUCCESS: editable texture workspace written to {args.out}')
        elif args.cmd=='import-textures':
            s=import_texture_workspace(args.workspace,args.image,args.out,args.alternate_mode)
            print(json.dumps(s,indent=2)); print(f'\nSUCCESS: rebuilt outfit files written to {args.out}')
        elif args.cmd=='make-example':
            s=make_diagnostic_example(args.preset,args.tpa,args.retexture,args.lara_mesh,args.out)
            print(json.dumps(s,indent=2)); print(f'\nSUCCESS: diagnostic example written to {args.out}')
    except (ToolError, OSError, struct.error) as e:
        print(f'ERROR: {e}',file=sys.stderr)
        return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
