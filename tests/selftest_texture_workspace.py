#!/usr/bin/env python3
from pathlib import Path
import argparse, hashlib, tempfile, sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tr_ngage_outfit as tool

def h(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
ap=argparse.ArgumentParser(description='Verify an export/import with no edits is byte-for-byte exact')
ap.add_argument('tpa',type=Path); ap.add_argument('retexture',type=Path); ap.add_argument('lara_mesh',type=Path)
a=ap.parse_args()
with tempfile.TemporaryDirectory() as d:
    w=Path(d)/'workspace'; o=Path(d)/'output'
    tool.export_texture_workspace(a.tpa,a.retexture,a.lara_mesh,w)
    tool.import_texture_workspace(w,None,o)
    if h(a.tpa)!=h(o/'new_tpage.tpa'): raise SystemExit('SELFTEST FAILED: TPA changed on no-edit round trip')
    if h(a.retexture)!=h(o/'retexture.dat'): raise SystemExit('SELFTEST FAILED: retexture.dat changed on no-edit round trip')
print('SELFTEST PASS: editable texture workspace round-trips byte-for-byte with no edits.')
