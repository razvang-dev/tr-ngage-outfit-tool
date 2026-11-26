#!/usr/bin/env python3
from pathlib import Path
import hashlib, tempfile, sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tr_ngage_outfit as tool

def h(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
root=Path(__file__).resolve().parents[1]
# Use the bundled example INSTALL inputs only as expected-output references; the source
# stock files themselves are passed as args so the test never silently substitutes them.
import argparse
ap=argparse.ArgumentParser()
ap.add_argument('stock_tpa',type=Path);ap.add_argument('stock_retexture',type=Path);ap.add_argument('lara_mesh',type=Path)
a=ap.parse_args()
expected={
 'arm-body-contrast':h(root/'examples/01_arm_body_contrast/INSTALL/retexture.dat'),
 'pants-belt-isolation':h(root/'examples/02_pants_belt_isolation/INSTALL/retexture.dat'),
}
for preset,eh in expected.items():
    with tempfile.TemporaryDirectory() as d:
        s=tool.make_diagnostic_example(preset,a.stock_tpa,a.stock_retexture,a.lara_mesh,Path(d))
        got=h(Path(d)/'retexture.dat')
        if got!=eh: raise SystemExit(f'{preset}: expected {eh}, got {got}')
        if h(Path(d)/'new_tpage.tpa')!=tool.STOCK_AOD_TPA_SHA256: raise SystemExit(f'{preset}: TPA mismatch')
        print(preset,'PASS',got)
print('EXAMPLE SELFTEST PASS')
