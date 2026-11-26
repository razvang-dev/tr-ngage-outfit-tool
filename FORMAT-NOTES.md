# TR N-Gage Outfit Tool v0.4.0 — reverse-engineered format notes

These are the N-Gage format assumptions implemented by v0.3.1.

## Runtime model

Classic Lara is the game's base state. When `deldata/retexture.dat` exists, the NAX code applies the optional outfit patch.

```text
base Lara / level data
       ↓
retexture.dat present?
       ├─ no  → Classic Lara remains
       └─ yes → replacement descriptor + face patch path
                     ↓
              new_tpage.tpa artwork
                     ↓
                custom Lara
```

`TOMBRAIDER.NAX` does not need to be modified for texture-only outfits.

## `new_tpage.tpa`

Exact size:

```text
32768 bytes
```

The NAX uploads it as:

```text
VRAM X      192
VRAM Y      256
width       64 16-bit words
height      256 rows
```

At 4 bpp, four texels fit in one 16-bit word, so this is one 256×256 indexed texture page.

Embedded CLUT areas:

```text
Table B: local TPA rows 177..191  = VRAM Y 433..447
Table A: local TPA rows 241..255  = VRAM Y 497..511
CLUT X:   VRAM 192..207           = 16 colors
```

The no-WAD editor preserves the raw page outside covered texture regions and rewrites only edited covered indices plus the relevant CLUT rows.

## `retexture.dat`

Exact known size:

```text
9006 bytes
```

Layout:

```text
0x0000  101 × 16-byte descriptor table A   1616 bytes
0x0650  101 × 16-byte descriptor table B   1616 bytes
0x0CA0  Lara face-patch stream              5774 bytes
```

Local texture code mapping:

```text
code 0   -> reserved absolute texture 1408
code 1   -> 1407
...
code 100 -> 1308
```

Physical descriptor record:

```text
record = 100 - localCode
```

`0xFFFF` is used as the safe "keep existing texture" code in the normal in-place patch path.

### 16-byte descriptor

The analyzed records use four packed 32-bit words. The low 16 bits carry texture coordinates and the first two high halves carry CLUT/TPAGE information.

Conceptually:

```text
word0: CLUT  | V0 | U0
word1: TPAGE | V1 | U1
word2: AUX   | V2 | U2
word3: AUX   | V3 | U3
```

Table A and Table B normally use the same palette-group number with different CLUT row bases. The stock AoD file has two known active descriptors (55 and 57) whose final packed word differs between A/B. v0.2 therefore preserves `retexture.dat` byte-for-byte in the editable-texture workflow instead of attempting to normalize those descriptors.

## Face-patch stream

The matching `lara.mesh` determines exactly how many patch bytes are consumed.

Quad:

```text
uint16 vertex[4]
uint16 textureCode
= 10 bytes
```

Triangle:

```text
uint16 vertex[3]
uint16 textureCode
= 8 bytes
```

Known N-Gage Lara totals:

```text
371 quads
258 triangles
629 textured faces
```

Therefore:

```text
371×10 + 258×8 = 5774 bytes
```

## `lara.mesh`

The file has 26 length-prefixed mesh records:

```text
uint32 wordCount
uint8  meshBlob[wordCount * 2]
```

Primary body meshes 0..14:

```text
0  pelvis
1  left thigh
2  left calf/knee
3  left foot/ankle
4  right thigh
5  right calf/knee
6  right foot/ankle
7  torso
8  right upper arm
9  right lower arm
10 right hand
11 left upper arm
12 left lower arm
13 left hand
14 head
```

Records 15..25 are pistol/magnum/Uzi/shotgun hand, holster/thigh and torso variants.

## Editable workspace format

Export creates `TRNGAGE_TEXTURE_WORKSPACE_1`.

Critical template files are hashed in `workspace.json`:

```text
template_new_tpage.tpa
template_retexture.dat
palette_map.bin
texture_reference.rgb
```

Import validates these hashes before rebuilding output.

`palette_map.bin` is 65536 bytes, one byte per editable pixel:

```text
0      unused
1..15  palette group 0..14
```

The editable RGB image does not alter UVs. It is simply converted back to per-group 4-bit indices and CLUTs.

## No-edit safety path

If the imported editable RGB image is identical to `texture_reference.rgb`, v0.2 does not requantize anything. It copies the template TPA and `retexture.dat` byte-for-byte.

This is regression-tested.

## Classic WAD path

The old-style WAD converter supports file ID 129. It searches for 15 consecutive Lara meshes with compatible vertex counts/topology, extracts source texture samples, packs them into the safe TPA area, allocates CLUT groups and generates the 101 descriptor entries plus patch stream.

This is the path that generated the successful TR1 beta Lara conversion.


## WAD2 source bridge (v0.3)

WAD2 is a **source format**, not an N-Gage runtime format. v0.3 reads Tomb Editor WAD2 container version 0 and the subset needed for Lara outfits:

```text
W2Textures / W2Txt / W2TxtData   embedded BGRA32 textures
W2Moveables / W2Moveable         object IDs
W2Mesh                             positions / normals / polygons
W2Polys                            triangle/quad texture + UV data
W2Bone2                            mesh/bone role metadata and translations
```

Tomb Editor polygon UVs in the tested WAD2 files are pixel-space floats rather than normalized 0..1 coordinates. The v0.3 converter rounds/clamps them to source texels, packs used regions into the N-Gage safe atlas rows, then creates ordinary N-Gage descriptors.

WAD2 texture pixels are BGRA32. Alpha below the selected threshold becomes N-Gage transparent index 0. Each used WAD2 source texture is assigned one N-Gage 16-color CLUT group in v0.3; source colors are quantized with weighted median cut in PSX 5-bit color space.

WAD2 geometry that does not match the N-Gage 15-mesh topology is not serialized by v0.3. See `docs/WAD2-GEOMETRY-LAB.md`.


## WAD2 uniform-source completion (v0.3.1)

If every used source texel is fully opaque and all source colors collapse to one PSX BGR555 value, UV differences are irrelevant. In this case WAD2 `fallback_mode=auto` may assign a valid source descriptor to topology-unmatched primary faces and all extra weapon/holster mesh faces. This is used by Gold/Midas-style skins. It is not applied to ordinary multi-color/transparent outfits.

## WAD2 arbitrary geometry serialization (v0.4)

v0.4 extends the WAD2 source bridge beyond topology-compatible skins.

For geometry mode, the selected 15-mesh `LARA_SKIN` is serialized directly into the external N-Gage `lara.mesh` record format:

```text
uint32 wordCount
int16  center[3]
int32  radius
int16  vertexCount
short4 positions[vertexCount]
short4 normals[vertexCount]
uint16 quadCount
(4*uint16 vertex + uint16 texture) * quadCount
uint16 triangleCount
(3*uint16 vertex + uint16 texture) * triangleCount
```

WAD2 Y is negated to match the established N-Gage mesh coordinate convention. WAD2 normals are normalized to fixed-point magnitude ~16300; missing normals are computed from polygon faces.

The generated face texture fields in `lara.mesh` are initialized to zero because `retexture.dat` supplies the final descriptor code for every face before the geometry is intended to render.

Unlike the shipped 9006-byte DAT, a custom-topology geometry DAT has a dynamic size:

```text
3232 descriptor bytes
+ 10 bytes per generated quad
+ 8 bytes per generated triangle
```

The TR5 development bundle contains 558 faces and produces an 8710-byte DAT. Its generated parser reaches exact EOF.

The first 15 records come directly from WAD2. The 11 weapon/holster roles are currently synthesized by cloning their semantic primary mesh, preserving structural validity until dedicated source variants are supported.
