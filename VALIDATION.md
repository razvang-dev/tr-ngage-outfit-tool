# Validation status — v0.4.0

## Previously in-game validated

- Magenta torso CLUT test.
- Converted TR1 beta Lara from classic WAD.
- Body/arm contrast diagnostic.
- Pants/belt isolation diagnostic.

These establish the N-Gage TPA / CLUT / retexture face mapping used by the converter.

## Regression validated in v0.3

### Classic WAD

The beta-Lara self-test still reproduces the known successful output byte-for-byte.

### Texture Editor

A no-edit export/import round trip reproduces the original TPA and DAT byte-for-byte.

### Body/accessory examples

Both v0.2.1 documented example DAT files are reproduced byte-for-byte.

### WAD2 — TR1 Lara Gold

Analysis result:

```text
selected object: 12 / LARA_SKIN
Grade A
15/15 vertex-count matches
335/375 topology matches = 89.3%
14/15 mesh position arrays exact after Y-axis sign conversion
```

Conversion result in the v0.3 regression environment:

```text
mapped primary faces: 335
primary fallback faces: 40
weapon/alternate fallback faces: 254
used source textures: 1
palette groups: 1
packed regions: 1
descriptors: 7
new_tpage.tpa: 32768 bytes
retexture.dat: 9006 bytes
retexture parser reaches exact EOF after 629 faces
```

The original v0.3 partial-coverage build was structurally valid, but the screenshots revealed Classic fallback fragments in the head and weapon/holster thigh variants. v0.3.1 fixes those gaps for uniform WAD2 skins. The full-coverage Gold build is now **in-game confirmed** at 629/629 custom faces with zero Classic fallback.

### WAD2 — TR5-style Lara

Analysis result:

```text
selected object: 12 / LARA_SKIN
Grade C
2/15 vertex-count matches
6/375 topology matches = 1.6%
recommended mode: geometry-replacement-required
```

The normal WAD2 converter correctly refuses this input. Geometry Lab export produces 15 OBJ body parts and the five source textures used by LARA_SKIN.

## Run the WAD2 regression

```bash
python tests/selftest_wad2.py TR1_Lara_Gold.wad2 TR5_Lara_Skeleton.wad2 lara.mesh
```

Expected final line:

```text
WAD2 SELFTEST PASS
```


## v0.3.1 Gold uniform-completion regression

`TR1_Lara_Gold.wad2` + reference `lara.mesh`, default WAD2 fallback mode `auto`:

- source topology matches remain 335 / 375;
- source texture is detected as fully opaque and uniform;
- 40 unmatched primary faces are completed with the Gold descriptor;
- all 254 extra weapon/holster faces are completed with the Gold descriptor;
- `retexture.dat` contains 629 custom codes, 0 `0xFFFF` fallbacks, and parses to exact EOF;
- output sizes remain 32768-byte TPA / 9006-byte DAT.

## In-game confirmation — WAD2 Gold full coverage

The v0.3.1 full-coverage Gold/Midas Lara build has now been tested in-game from multiple views. The previously visible Classic fragments are gone: the head, torso, pelvis/thigh/holster variants, limbs, and weapon-related replacement meshes all render with the Gold source treatment.

Confirmed output characteristics:

```text
primary faces:          375 / 375 custom
weapon/holster faces:   254 / 254 custom
total faces:            629 / 629 custom
Classic fallback:         0
new_tpage.tpa:        32768 bytes
retexture.dat:         9006 bytes
```

Reference screenshots are stored under:

```text
docs/screenshots/WAD2-Gold-FullCoverage/
```

This makes the texture-only WAD2 conversion path hardware/in-game proven for a Grade-A uniform-color `LARA_SKIN`.

## v0.4 geometry serializer regression

The v0.4 serializer is regression-tested with `TR5_Lara_Skeleton.wad2`.

Expected source SHA-256:

```text
d3ebd11f9be65570971549cadf297e0abec18576a85565987963852f1678ea58
```

Expected generated bundle:

```text
26 mesh records
405 primary WAD2 faces
153 synthesized weapon/holster-variant faces
558 total faces
68 descriptors
5 source textures
26 packed source regions
42 atlas rows

lara.mesh       15038 bytes
retexture.dat    8710 bytes
new_tpage.tpa   32768 bytes
```

Regression hashes:

```text
lara.mesh
 e39122db6c9356d7381f6a96f007621360f85d2f1e420e0e66476a001c33e17e

retexture.dat
 bc8f24f5822482ed345180c6fdfcc7c12a82db271eb000736748db08b9661b86

new_tpage.tpa
 b0ce2d74a0b024da33d4b2c9192c3451b84b506649f605a70f53c0e08e8b3707
```

`tests/selftest_geometry_serializer.py` verifies:

- all 26 records parse back through the N-Gage parser;
- the first 15 position arrays exactly equal the WAD2 positions after Y-axis conversion;
- per-mesh face counts equal the WAD2 source;
- generated normal magnitudes are ~16300;
- the matching retexture stream consumes all 558 generated faces and reaches exact EOF;
- all 558 face codes are custom (no `0xFFFF` fallback).

This is **format/serializer validation**, not yet game-wide runtime validation. The stock normal-level retexture path still expects resident Lara topology; runtime activation remains the next milestone.
