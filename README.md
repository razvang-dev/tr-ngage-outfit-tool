# TR N-Gage Outfit Tool v0.4.0

A research/modding toolchain for custom Lara outfits in the original Nokia N-Gage release of **Tomb Raider**.

Developed by **RazvanG**.

The project now supports three proven/practical texture workflows plus an experimental geometry serializer:

```text
1. Classic WAD
custom.wad + original lara.mesh
        ↓
new_tpage.tpa + retexture.dat

2. WAD2 / Tomb Editor
compatible LARA_SKIN.wad2 + original lara.mesh
        ↓
new_tpage.tpa + retexture.dat

3. No-WAD texture editing
working N-Gage outfit
        ↓ Export Textures
editable 256×256 PNG
        ↓ edit in Photoshop/GIMP/etc.
        ↓ Import Textures
new_tpage.tpa + retexture.dat
```

For WAD2 files whose geometry does **not** match N-Gage Lara, v0.4 can now both export a Geometry Lab and serialize a real experimental N-Gage `lara.mesh` + matching texture/retexture stream. The serializer is not game-wide install-safe yet; runtime activation is the next milestone.

## What has been proven in-game

The reverse-engineered runtime model is established by successful tests:

- Classic Lara is the game's base state.
- `retexture.dat` is the optional runtime face/texture override.
- `new_tpage.tpa` contains the 4-bpp outfit page + embedded CLUTs.
- changing a specific CLUT produced the expected magenta torso;
- a converted external TR1 beta Lara WAD rendered in-game;
- the no-WAD Texture Editor can export/import the outfit page;
- face-level pelvis edits can isolate the belt from the pants even though both belong to the same pelvis mesh object.

See `docs/BODY-ACCESSORY-SEPARATION.md` for the diagnostic examples.

## New in v0.4

### Experimental WAD2 geometry serializer

v0.4 adds `build-wad2-geometry`, which writes arbitrary 15-mesh WAD2 `LARA_SKIN` geometry into the decoded 26-record N-Gage external `lara.mesh` format and generates a matching TPA + dynamic-length retexture stream. The TR5 development WAD2 serializes to 558 custom faces and 68 descriptors with exact parser round-trip validation. See `docs/GEOMETRY-SERIALIZER.md`.

### WAD2 fallback completion

v0.3.1 adds an `auto` fallback mode. When a WAD2 Lara skin is a fully opaque single color (for example TR1 Gold/Midas Lara), the tool can safely apply that color to topology-mismatched head/torso faces and all 11 N-Gage weapon/holster mesh variants. Ordinary textured outfits still use topology-safe mapping and Classic fallback until geometry/UV coverage is available. See `docs/WAD2-COVERAGE-FALLBACK.md`.

## WAD2 Lab

- Reads Tomb Editor WAD2 container version 0.
- Reads embedded BGRA32 textures.
- Reads moveables, 15 Lara meshes, polygon UVs and Bone2 metadata.
- Prefers TombEngine object 12 (`LARA_SKIN`) when available.
- Grades WAD2 compatibility before conversion.
- Converts topology-compatible WAD2 skins to N-Gage TPA + DAT.
- Exports geometry-incompatible WAD2 Lara skins as OBJ parts + source textures.

The supplied development examples classify as:

```text
TR1_Lara_Gold.wad2      Grade A   335/375 topology matches
TR5_Lara_Skeleton.wad2  Grade C     6/375 topology matches
TEN_Lara.wad2           Grade C    animation/skeleton object
```

See `docs/WAD2-GUIDE.md` and `docs/WAD2-GEOMETRY-LAB.md`.

## Requirements

- Python 3.9+ recommended.
- No third-party Python modules are required.
- Your own original N-Gage `deldata/lara.mesh` for conversion/compatibility reference.
- A source WAD/WAD2, or existing N-Gage outfit files for no-WAD editing.

## GUI

Windows:

```text
run_gui.bat
```

Linux/WSL:

```bash
./run_gui.sh
```

Tabs:

- **Classic WAD** — hardware-proven classic WAD converter.
- **WAD2 Lab** — analyze, convert compatible WAD2 skins, export OBJ geometry, or build the experimental v0.4 N-Gage geometry bundle.
- **Texture Editor** — export/import editable N-Gage textures with no WAD required.
- **Examples** — body/accessory diagnostic reference builds.

## WAD2 quick start

Analyze:

```bash
python tr_ngage_outfit.py analyze-wad2 outfit.wad2 --lara-mesh lara.mesh
```

If the result is Grade A/B:

```bash
python tr_ngage_outfit.py convert-wad2 outfit.wad2 \
    --lara-mesh lara.mesh \
    -o output
```

If the result is Grade C, first export/study it:

```bash
python tr_ngage_outfit.py export-wad2-model outfit.wad2 \
    --lara-mesh lara.mesh \
    -o geometry_lab
```

Then the v0.4 serializer can build the experimental game-format bundle:

```bash
python tr_ngage_outfit.py build-wad2-geometry outfit.wad2 \
    --lara-mesh lara.mesh \
    -o geometry_bundle
```

Read `geometry_bundle/EXPERIMENTAL-NOTICE.txt` before attempting any test.

## Classic WAD quick start

```bash
python tr_ngage_outfit.py convert-wad outfit.wad \
    --lara-mesh lara.mesh \
    -o output
```

## No-WAD Texture Editor

```bash
python tr_ngage_outfit.py export-textures new_tpage.tpa \
    --retexture retexture.dat \
    --lara-mesh lara.mesh \
    -o workspace
```

Edit `workspace/texture_edit.png`, do not resize it, then:

```bash
python tr_ngage_outfit.py import-textures workspace \
    --image workspace/texture_edit.png \
    -o rebuilt
```

## Install generated texture-only outfits

**Back up originals first.**

Copy:

```text
new_tpage.tpa
retexture.dat
```

to:

```text
E:\System\Apps\tombraider\data\deldata\
```

Leave `lara.mesh` unchanged unless you are deliberately testing a future geometry build.

For a new conversion, test an early/normal level with Lara unarmed first.

## Important geometry limitation

v0.4 now **does emit** a real N-Gage-format `lara.mesh` for arbitrary WAD2 Lara geometry, together with matching `new_tpage.tpa` and a topology-matched `retexture.dat`.

The remaining limitation is runtime activation: the stock NAX uses external `lara.mesh` only on its special replacement path, while ordinary levels patch resident Lara geometry. Because a custom-topology retexture stream no longer matches those resident face counts, geometry bundles are currently **special-path laboratory output, not normal installable outfits**.

See `docs/GEOMETRY-SERIALIZER.md` and `docs/WAD2-GEOMETRY-LAB.md`.

## Documentation

- `docs/USER-MANUAL.md`
- `docs/TEXTURE-EDITING-GUIDE.md`
- `docs/BODY-ACCESSORY-SEPARATION.md`
- `docs/WAD2-GUIDE.md`
- `docs/WAD2-GEOMETRY-LAB.md`
- `docs/GEOMETRY-SERIALIZER.md`
- `docs/PROJECT-ROADMAP.md`
- `FORMAT-NOTES.md`
- `VALIDATION.md`

## Bundled diagnostic examples

The two diagnostic examples retain their modified `retexture.dat` files and research exports. Use your own unchanged stock AoD `new_tpage.tpa`; it is not distributed in this public package. See [examples/README.md](examples/README.md) for installation and regeneration instructions.

## Regression tests

Classic beta-WAD regression:

```bash
python tests/selftest_beta.py TR1betastuff.wad lara.mesh
```

No-edit Texture Editor round trip:

```bash
python tests/selftest_texture_workspace.py new_tpage.tpa retexture.dat lara.mesh
```

Diagnostic examples:

```bash
python tests/selftest_examples.py stock_new_tpage.tpa stock_retexture.dat lara.mesh
```

WAD2 texture bridge:

```bash
python tests/selftest_wad2.py TR1_Lara_Gold.wad2 TR5_Lara_Skeleton.wad2 lara.mesh
```

WAD2 geometry serializer:

```bash
python tests/selftest_geometry_serializer.py TR5_Lara_Skeleton.wad2 lara.mesh
```

## Status

v0.4.0 keeps the in-game-confirmed 629/629 Gold/Midas WAD2 texture path and adds the first validated WAD2 → N-Gage geometry serializer. The serializer is complete enough to generate/parse real 26-record `lara.mesh` bundles; the next development branch is game-wide NAX runtime activation for that custom topology.

## License

Original project software and associated original documentation are licensed under the [MIT License](LICENSE). Game-derived reference material is excluded from that grant; see [THIRD-PARTY-NOTICE.md](THIRD-PARTY-NOTICE.md).

## Credits & Greetings

To everyone keeping the Nokia N-Gage alive, mupf.dev & Vanessa Summers!

Visit the official Nokia N-Gage Discord at [https://discord.gg/wm7bYRErfZ](https://discord.gg/wm7bYRErfZ)

PS: This is AI slop :P
