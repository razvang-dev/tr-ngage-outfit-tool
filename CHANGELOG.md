# Changelog

## v0.4.0

### Public source release packaging

- Omitted the two unchanged stock AoD texture pages from bundled examples; users supply their own stock page.
- Preserved all source code, diagnostic modifications, research exports, screenshots and self-tests.
- Added MIT license, third-party notice and Git ignore rules; updated example instructions and checksums.
- Removed generated Python bytecode caches from distribution; no functional code changes.

### Development changes

- Renamed example/reference screenshots to orientation-neutral `image_XX` filenames to avoid incorrect front/rear/side labels.

- Added the first experimental WAD2 → N-Gage `lara.mesh` serializer.
- Arbitrary 15-mesh WAD2 `LARA_SKIN` geometry can now be written into the 26-record N-Gage external mesh format.
- Added W2MeshSphere/BBox parsing and fixed-point normal conversion.
- Geometry mode builds its own WAD2 UV atlas, descriptors and dynamic-length `retexture.dat` stream rather than matching stock topology.
- Added synthetic geometry-safe versions of all 11 weapon/holster record roles by cloning their semantic primary body parts.
- Added `build-wad2-geometry` CLI command and **Build EXP Geometry** GUI action.
- Added `tests/selftest_geometry_serializer.py`.
- TR5 development regression: 405 primary faces + 153 synthesized variant faces = 558 custom faces, 68 descriptors, exact parser round trip.
- Geometry output remains special-path laboratory output until NAX runtime activation is implemented for ordinary levels.

## v0.3.1

- Hardware/emulator feedback from the first WAD2 Gold test identified visible Classic fallback fragments.
- Added `auto`, `classic`, and `uniform` WAD2 fallback modes.
- `auto` now detects fully opaque single-color WAD2 skins (such as TR1 Gold/Midas Lara) and safely completes all unmatched primary plus weapon/holster variant faces.
- Gold regression now reaches 629/629 custom face records with zero `0xFFFF` fallbacks.
- The Gold screenshots also proved that separate holster/thigh variant meshes are active during normal gameplay.
- Added `docs/WAD2-COVERAGE-FALLBACK.md`.
- Full-coverage Gold/Midas WAD2 build is now in-game confirmed from multiple views.
- Archived the confirmation screenshots under `docs/screenshots/WAD2-Gold-FullCoverage/`.
- Updated README credits and project status.

## v0.3.0

### WAD2

- Added `wad2_support.py` Tomb Editor WAD2 reader.
- Added embedded BGRA32 texture extraction.
- Added moveable, mesh, polygon UV and Bone2 parsing.
- Added `analyze-wad2` compatibility grading.
- Added semantic preference for object 12 (`LARA_SKIN`) over object 14 (`LARA_SCREAM`) and object 0 (`LARA`).
- Added `convert-wad2` texture/topology conversion for Grade A/B skins.
- Added WAD2 alpha-threshold handling.
- Added per-source-texture 15-color palette generation.
- Added WAD2 UV-region packing into the N-Gage safe texture-page area.
- Added `export-wad2-model` OBJ + RGBA texture Geometry Lab export.
- Added WAD2 Lab GUI tab.
- Added WAD2 regression test and compatibility-report examples.

### Documentation

- Added `docs/WAD2-GUIDE.md`.
- Added `docs/WAD2-GEOMETRY-LAB.md`.
- Added `docs/PROJECT-ROADMAP.md`.
- Updated main documentation for the three source workflows: classic WAD, WAD2, and no-WAD editing.

### Preserved from v0.2.1

- Classic WAD hardware-proven converter.
- No-WAD editable texture workspaces.
- Body/accessory region diagnostic examples.
- Belt/pants pelvis-face isolation preset.

## v0.2.1

- Consolidated body/accessory diagnostic examples.
- Added Examples GUI tab and diagnostic preset generator.
- Added named AoD region/preset groundwork.

## v0.2

- Added WAD-independent texture export/import workspace.
- Added editable PNG/BMP workflow and palette-group diagnostics.

## v0.1

- First packaged classic WAD converter reproducing the successful beta-Lara conversion.
