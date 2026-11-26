# Project roadmap after v0.4

The project has moved beyond a one-purpose converter. It is becoming a small N-Gage Tomb Raider outfit/modding SDK.

## v0.3 — WAD2 bridge and geometry lab

Implemented:

- WAD2 parser for embedded textures, moveables, meshes, UVs and Bone2 metadata;
- automatic `LARA_SKIN` candidate selection;
- compatibility grades A/B/C;
- WAD2 texture/topology converter for compatible skins;
- WAD2 OBJ + texture Geometry Lab export;
- GUI WAD2 Lab tab;
- regression classification for TR1 Gold vs. TR5-style geometry;
- classic WAD, no-WAD Texture Editor, body/accessory examples remain intact.

## v0.3.x — polish before geometry

Recommended:

- display named BODY / BELT / BACKPACK / HOLSTERS / BOOTS regions in the Texture Editor;
- interactive visibility/highlight masks;
- finish all 11 weapon/holster texture mappings;
- reconstruct the alternate/underwater CLUT bank instead of duplicating normal palettes;
- improve atlas packing and palette diagnostics for more complex WAD2 skins;
- add a portable project/workspace format that stores source provenance, region labels and test status.

## v0.4 — experimental geometry serializer

Implemented:

- WAD2 15-mesh body → real N-Gage 26-record `lara.mesh`;
- fixed-point normals conversion/validation;
- arbitrary custom face topology + descriptor stream generation;
- direct WAD2 UV atlas generation;
- synthesized 11 weapon/holster record roles;
- exact parser/stream regression testing with the TR5 development WAD2;
- explicit EXPERIMENTAL labeling because game-wide runtime activation is not finished.

## v0.5 — game-wide custom geometry

- extend the NAX retexture path to install replacement meshes on normal levels;
- avoid touching unrelated Tomb Raider code;
- preserve Classic fallback behavior when custom files are absent;
- build and validate all weapon-specific variants.

## v0.6 — native in-game outfit selector

Return to the clean long-term goal:

```text
Options
  Outfit: Classic / AoD / Custom 1 / Custom 2
```

The native game would select an outfit configuration directly, eliminating the external TRLoader for outfit switching. TRLoader can remain useful as a standalone compatibility/launcher utility.

## v1.0 — user-facing modding package

A mature release should have:

- Classic WAD import;
- WAD2 import;
- no-WAD texture editing;
- named body/accessory regions;
- optional geometry import;
- weapon variants;
- normal + underwater palettes;
- project manifest and validation report;
- one-click build of an installable outfit directory;
- reversible installation instructions;
- regression suite for known hardware-tested outfits.

## Longer-term research ideas

- `.trngo` project/archive format containing generated outfit files + metadata, without requiring source WADs;
- Blender helper/export script using the documented 15 body parts and 11 variant roles;
- visual descriptor/UV inspector;
- side-by-side N-Gage / WAD / WAD2 mesh comparison;
- automatic detection of belt/backpack/holster regions from texture/face usage;
- multiple custom outfit slots if the NAX loader and native Options-menu work make it practical.
