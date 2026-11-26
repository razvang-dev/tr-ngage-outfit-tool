# Experimental WAD2 → N-Gage geometry serializer — v0.4

v0.4 adds the first real writer for the external N-Gage `lara.mesh` format.

This is deliberately separated from the already-proven texture-only paths. A texture-only outfit can remain completely stock-executable and should continue using `convert-wad`, `convert-wad2`, or the no-WAD Texture Editor.

## Command

```bash
python tr_ngage_outfit.py build-wad2-geometry source.wad2 \
    --lara-mesh original_lara.mesh \
    -o geometry_bundle
```

GUI: **WAD2 Lab → Build EXP Geometry**.

The original N-Gage `lara.mesh` is used as the semantic/reference layout for the 26 record roles; it is not used as the generated geometry.

## Output

```text
lara.mesh
new_tpage.tpa
retexture.dat
manifest.json
patch_summary.csv
variant_map.csv
atlas_layout.csv
atlas_preview.png
atlas_preview_4x.png
EXPERIMENTAL-NOTICE.txt
```

## What is actually serialized

The selected WAD2 `LARA_SKIN` supplies the first 15 N-Gage records:

```text
 0 pelvis
 1 left thigh
 2 left calf
 3 left foot
 4 right thigh
 5 right calf
 6 right foot
 7 torso
 8 right upper arm
 9 right lower arm
10 right hand
11 left upper arm
12 left lower arm
13 left hand
14 head
```

WAD2 coordinates are converted to the N-Gage convention by flipping Y. Positions are rounded to signed 16-bit mesh coordinates.

WAD2 vertex normals are converted to the same fixed-point convention observed in the shipped N-Gage file: non-zero normals are normalized to magnitude approximately **16300** and stored as `(x,y,z,0)` signed 16-bit vectors. If WAD2 normals are absent, the tool computes averaged vertex normals from polygon faces.

The WAD2 `W2MeshSphere` center/radius is used for each N-Gage mesh record when available. If it is missing, the converter generates a conservative bounding sphere from the mesh vertices.

Triangles and quads are preserved with their source WAD2 vertex indices. N-Gage records store quads first, then triangles, so v0.4 reorders polygon storage by primitive type while keeping relative source order within each type.

## Texture/UV stream

Unlike the v0.3 topology bridge, geometry mode does not need to match source faces to the stock N-Gage model.

Every WAD2 Lara polygon contributes its own source UV mapping. The converter:

1. identifies unique source texture rectangles;
2. packs them into the safe part of the 256×256 4-bpp N-Gage page;
3. assigns one 16-color CLUT group per WAD2 source texture;
4. creates/reuses N-Gage 16-byte UV/CLUT descriptors;
5. writes a `retexture.dat` face stream that exactly matches the generated `lara.mesh` topology.

The TR5 development WAD2 currently uses:

```text
5 source textures
26 unique packed source regions
68 N-Gage texture descriptors
```

which fits comfortably inside the N-Gage limits of 15 palette groups and 101 replacement descriptors.

## 11 weapon/holster records

The external N-Gage `lara.mesh` format contains another 11 records after the primary body. The WAD2 `LARA_SKIN` used for development does not contain corresponding pistol/magnum/Uzi/shotgun meshes.

v0.4 therefore synthesizes geometry-safe placeholders by cloning the corresponding primary body part:

```text
pistol: left/right hands + left/right thighs
magnum: left/right hands
Uzi:    left/right hands
shotgun:left/right hands + torso
```

This keeps the generated 26-record structure valid and gives every face a matching texture descriptor, but it does **not** recreate weapon-specific holsters or weapon geometry. That is a later geometry milestone.

## Critical runtime limitation

The serializer is working, but game-wide activation is not solved yet.

The stock N-Gage game uses the external `lara.mesh` only on a previously identified special replacement path. Ordinary levels keep Lara geometry already resident in the level and apply `retexture.dat` to that resident topology.

A geometry-mode `retexture.dat` follows the new WAD2 face counts. For example, the TR5 development bundle has **558** generated face records rather than the shipped **629**. It therefore must **not** be left installed while an ordinary level consumes the stock Lara topology—the streams would no longer line up.

For that reason v0.4 geometry output is explicitly a **serializer / special-path laboratory**, not a normal installable outfit yet.

The next engineering milestone is the runtime patch: make the already-reversed NAX retexture loader install the external generated mesh table and its matching stream consistently in ordinary levels. Once that is working, the same serializer becomes the basis of real game-wide WAD2 geometry support.

## TR5 regression bundle

The development WAD2 (`TR5_Lara_Skeleton.wad2`) currently serializes to:

```text
26 lara.mesh records
405 primary body faces
153 synthesized variant faces
558 faces total
68 descriptors
lara.mesh       15038 bytes
retexture.dat    8710 bytes
new_tpage.tpa   32768 bytes
```

All three outputs round-trip through the tool's parsers. The matching retexture stream reaches exact EOF with 558/558 custom face codes and no `0xFFFF` fallback records.
