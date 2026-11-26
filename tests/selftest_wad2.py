#!/usr/bin/env python3
from pathlib import Path
import argparse, tempfile, sys, json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tr_ngage_outfit as tool

ap=argparse.ArgumentParser(description='Exercise v0.3.1 WAD2 analysis/conversion/geometry-lab paths')
ap.add_argument('gold_wad2',type=Path,help='Topology-compatible TR1 Gold LARA_SKIN WAD2')
ap.add_argument('tr5_wad2',type=Path,help='Geometry-different TR5-style LARA_SKIN WAD2')
ap.add_argument('lara_mesh',type=Path)
a=ap.parse_args()

g=tool.analyze_wad2_file(a.gold_wad2,a.lara_mesh)
if g['selected_object_id']!=12 or g['selected_grade']!='A' or g['selected_topology_matches']!=335:
    raise SystemExit('WAD2 SELFTEST FAILED: TR1 Gold compatibility classification changed')
with tempfile.TemporaryDirectory() as d:
    # Preserve the old topology-only behavior explicitly.
    classic=Path(d)/'gold_classic'
    mc=tool.convert_wad2(a.gold_wad2,a.lara_mesh,classic,fallback_mode='classic')
    rc=tool.inspect_retexture(classic/'retexture.dat',a.lara_mesh)
    if not rc.get('exact_eof') or rc.get('custom_codes_0_100')!=335:
        raise SystemExit('WAD2 SELFTEST FAILED: classic-fallback regression changed')
    # New default auto mode recognizes the 4x4 single-color Gold source and completes every face,
    # including unmatched head/torso topology and all 11 weapon/holster variant meshes.
    out=Path(d)/'gold_auto'
    m=tool.convert_wad2(a.gold_wad2,a.lara_mesh,out)
    if (out/'new_tpage.tpa').stat().st_size!=32768 or (out/'retexture.dat').stat().st_size!=9006:
        raise SystemExit('WAD2 SELFTEST FAILED: converted sizes are wrong')
    r=tool.inspect_retexture(out/'retexture.dat',a.lara_mesh)
    if not r.get('exact_eof') or r.get('custom_codes_0_100')!=629 or r.get('fallback_ffff')!=0:
        raise SystemExit('WAD2 SELFTEST FAILED: uniform completion did not cover all 629 faces')
    if not m.get('uniform_source_completion') or m.get('primary_fallback_faces')!=0 or m.get('weapon_extra_faces_fallback')!=0:
        raise SystemExit('WAD2 SELFTEST FAILED: Gold manifest does not report full uniform completion')
    print('TR1 Gold WAD2 conversion PASS',m['sha256_tpa'],m['sha256_retexture'])

t=tool.analyze_wad2_file(a.tr5_wad2,a.lara_mesh)
if t['selected_object_id']!=12 or t['selected_grade']!='C' or t['recommended_mode']!='geometry-replacement-required':
    raise SystemExit('WAD2 SELFTEST FAILED: TR5 geometry-required classification changed')
try:
    with tempfile.TemporaryDirectory() as d:
        tool.convert_wad2(a.tr5_wad2,a.lara_mesh,Path(d))
except tool.ToolError:
    pass
else:
    raise SystemExit('WAD2 SELFTEST FAILED: geometry-incompatible WAD2 was not rejected')
with tempfile.TemporaryDirectory() as d:
    out=Path(d)/'tr5lab'; e=tool.export_wad2_model(a.tr5_wad2,a.lara_mesh,out)
    if len(list((out/'parts').glob('*.obj')))!=15 or len(list((out/'textures').glob('*.png')))!=5:
        raise SystemExit('WAD2 SELFTEST FAILED: geometry lab export is incomplete')
    print('TR5 WAD2 geometry lab PASS',e['topology_coverage'])
print('WAD2 SELFTEST PASS')
