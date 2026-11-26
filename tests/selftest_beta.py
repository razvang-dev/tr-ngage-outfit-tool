#!/usr/bin/env python3
from pathlib import Path
import argparse, hashlib, json, shutil, tempfile, sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tr_ngage_outfit as tool

def h(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
ap=argparse.ArgumentParser(description='Reproduce the in-game-confirmed Beta Lara Test 2 output')
ap.add_argument('wad',type=Path);ap.add_argument('lara_mesh',type=Path)
a=ap.parse_args()
ref=json.loads((Path(__file__).resolve().parents[1]/'reference/BETA-INGAME-CONFIRMED.json').read_text())
if h(a.wad)!=ref['source_wad_sha256']: raise SystemExit('Source WAD hash does not match the in-game-confirmed beta WAD')
if h(a.lara_mesh)!=ref['ngage_lara_mesh_sha256']: raise SystemExit('lara.mesh hash does not match the reverse-engineered reference')
with tempfile.TemporaryDirectory() as d:
    s=tool.convert(a.wad,a.lara_mesh,Path(d))
    got_tpa=h(Path(d)/'new_tpage.tpa');got_rt=h(Path(d)/'retexture.dat')
    print('new_tpage.tpa',got_tpa)
    print('retexture.dat ',got_rt)
    if got_tpa!=ref['expected_new_tpage_tpa_sha256'] or got_rt!=ref['expected_retexture_dat_sha256']:
        raise SystemExit('SELFTEST FAILED: generated hashes differ')
print('SELFTEST PASS: byte-for-byte reproduction of the in-game-confirmed Beta Lara conversion.')
