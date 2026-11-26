#!/usr/bin/env python3
from pathlib import Path
import argparse, hashlib, json, math, sys, tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tr_ngage_outfit as tool
import wad2_support as wad2

def h(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

ap=argparse.ArgumentParser(description='Regression-test the v0.4 WAD2 geometry serializer with the TR5-style development WAD2')
ap.add_argument('tr5_wad2',type=Path);ap.add_argument('reference_lara_mesh',type=Path)
a=ap.parse_args()
expected_source='d3ebd11f9be65570971549cadf297e0abec18576a85565987963852f1678ea58'
if h(a.tr5_wad2)!=expected_source: raise SystemExit('TR5 development WAD2 hash does not match the regression source')
with tempfile.TemporaryDirectory() as td:
    out=Path(td);m=tool.build_wad2_geometry(a.tr5_wad2,a.reference_lara_mesh,out)
    if m['records']!=26 or m['primary_faces']!=405 or m['total_faces']!=558 or m['descriptor_count']!=68: raise SystemExit('Unexpected geometry manifest counts')
    if m['lara_mesh_size']!=15038 or m['retexture_size']!=8710 or m['tpa_size']!=32768: raise SystemExit('Unexpected generated file sizes')
    if m['sha256_lara_mesh']!='e39122db6c9356d7381f6a96f007621360f85d2f1e420e0e66476a001c33e17e': raise SystemExit('lara.mesh regression hash mismatch')
    if m['sha256_retexture']!='bc8f24f5822482ed345180c6fdfcc7c12a82db271eb000736748db08b9661b86': raise SystemExit('retexture.dat regression hash mismatch')
    if m['sha256_tpa']!='b0ce2d74a0b024da33d4b2c9192c3451b84b506649f605a70f53c0e08e8b3707': raise SystemExit('new_tpage.tpa regression hash mismatch')
    # Compare first 15 generated position arrays directly with WAD2 positions after the established Y flip.
    W=wad2.load(a.tr5_wad2);ref=tool.parse_ngage_lara(a.reference_lara_mesh);cand=tool.find_wad2_lara_skin(W,ref)
    gen=tool.parse_ngage_lara(out/'lara.mesh')
    for mi,sm in enumerate(cand['moveable']['meshes']):
        expect=[(round(x),round(-y),round(z),0) for x,y,z in sm['positions']]
        if gen[mi]['positions']!=expect: raise SystemExit(f'mesh {mi} generated positions do not match WAD2 source')
        if len(gen[mi]['quads'])+len(gen[mi]['triangles'])!=len(sm['polygons']): raise SystemExit(f'mesh {mi} polygon count mismatch')
        mags=[math.sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]) for n in gen[mi]['normals'] if n[:3]!=(0,0,0)]
        if mags and not all(16295<=x<=16305 for x in mags): raise SystemExit(f'mesh {mi} normal magnitude out of expected range')
    rt=tool.inspect_retexture(out/'retexture.dat',out/'lara.mesh')
    if not rt.get('exact_eof') or rt.get('faces')!=558 or rt.get('fallback_ffff')!=0: raise SystemExit('generated retexture stream validation failed')
print('SELFTEST PASS: WAD2 geometry serializer reproduced the TR5 development bundle and round-tripped all 26 N-Gage mesh records.')
