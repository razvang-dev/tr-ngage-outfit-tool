# WAD2 support — v0.3

v0.3 adds the first Tomb Editor / TombEngine-style **WAD2** pipeline to TR N-Gage Outfit Tool.

The key design decision is that WAD2 files are classified before conversion. Not every `LARA_SKIN` can be represented by the existing N-Gage mesh topology.

## Compatibility grades

The analyzer compares the 15 WAD2 Lara meshes with the 15 primary N-Gage Lara meshes.

- **Grade A — texture-convert supported**: topology is close enough that most WAD2 face textures/UVs can be moved onto the existing N-Gage geometry. Unmatched faces fall back to Classic textures.
- **Grade B — texture-convert with fallback**: still usable for an experiment, but more of the outfit will fall back.
- **Grade C — geometry replacement required**: the source has substantially different vertex/face topology. v0.3 refuses to generate misleading installable files; use Geometry Lab export instead.

The current thresholds are intentionally conservative:

```text
Grade A: >= 80% topology match and >= 13/15 vertex-count matches
Grade B: >= 70% topology match and >= 10/15 vertex-count matches
Grade C: everything else
```

## TombEngine role hints

For WAD2 files using the TombEngine catalog used by the supplied test files:

```text
object 0   LARA / animation-skeleton
object 12  LARA_SKIN
object 14  LARA_SCREAM
```

The tool prefers object 12 when it is present. `--object-id` can override automatic selection.

## Analyze first

GUI: **WAD2 Lab → Analyze WAD2**

CLI:

```bash
python tr_ngage_outfit.py analyze-wad2 outfit.wad2 --lara-mesh lara.mesh
```

A useful result looks like:

```text
selected_object_id: 12
selected_grade: A
recommended_mode: texture-convert-supported
selected_topology_matches: 335 / 375
```

A modern/different-geometry outfit may instead report:

```text
selected_grade: C
recommended_mode: geometry-replacement-required
```

## Convert a compatible WAD2

```bash
python tr_ngage_outfit.py convert-wad2 outfit.wad2 \
    --lara-mesh lara.mesh \
    -o output
```

The converter:

1. finds the best 15-mesh `LARA_SKIN` candidate;
2. matches source polygons to N-Gage Lara faces by topology;
3. reorders source UVs into N-Gage face vertex order without changing N-Gage winding;
4. extracts only used source texture regions from embedded WAD2 BGRA textures;
5. packs those regions into the safe portion of the 256×256 N-Gage texture page;
6. assigns one 16-color palette group per used WAD2 source texture;
7. builds the 101-entry descriptor banks;
8. emits a complete 629-face `retexture.dat` stream;
9. leaves unmatched and weapon-variant faces on Classic fallback.

Output:

```text
new_tpage.tpa
retexture.dat
atlas_preview.png
atlas_preview_4x.png
atlas_layout.csv
face_mapping.csv
patch_summary.csv
manifest.json
INSTALL.txt
```

### Alpha

WAD2 textures are BGRA32. By default alpha values below `128` become transparent index 0:

```bash
--alpha-threshold 128
```

## Current WAD2 regression examples

The package includes **analysis reports only** under:

```text
examples/wad2_compatibility_reports/
```

The supplied development files produced these useful cases:

### TR1 Lara Gold WAD2

- object 12 selected as `LARA_SKIN`
- 15/15 vertex-count matches
- 335/375 topology matches (89.3%)
- Grade A
- one source texture
- conversion succeeds with 335 custom faces and 40 primary Classic fallbacks

This is an excellent first WAD2 hardware test because the source is visually obvious and geometry-compatible.

### TR5-style Lara WAD2

- object 12 selected as `LARA_SKIN`
- 2/15 vertex-count matches
- 6/375 topology matches (1.6%)
- Grade C
- five source texture pages

This is exactly the kind of file the future geometry branch is meant to support.

### TEN Lara animation WAD2

Object 0 is the Lara animation/skeleton object, not a compatible N-Gage skin. It is classified Grade C for texture conversion.

## What v0.3 does not do yet

WAD2 support in v0.3 does **not**:

- synthesize a new N-Gage `lara.mesh` from arbitrary geometry;
- alter the NAX runtime to use replacement geometry in every level;
- generate weapon-specific WAD2 mesh variants;
- reproduce source normal/underwater palette differences;
- optimize very large/fragmented WAD2 UV layouts beyond the current safe shelf packer.

Those are intentional next-stage tasks, not hidden failures.

## Hardware status

The TR1 Gold/Midas `LARA_SKIN` full-coverage conversion is now in-game confirmed. With v0.3.1 `auto` fallback on the uniform source, all 629 Lara face records—including the 254 weapon/holster variant faces—render with the custom Gold descriptor and no Classic fallback fragments remain.
