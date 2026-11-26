# TR N-Gage Outfit Tool v0.3.0 — User Manual

## 1. Purpose

TR N-Gage Outfit Tool now has three main jobs:

1. convert a compatible classic Tomb Raider WAD into an N-Gage Lara outfit;
2. analyze/convert Tomb Editor WAD2 `LARA_SKIN` assets when their topology is compatible, or export them to the Geometry Lab when it is not;
3. edit an already-working N-Gage outfit directly in a normal image editor, with no WAD required.

The workflows share the same reverse-engineered N-Gage TPA / descriptor / face-patch backend.

---

## 2. The three workflows side-by-side

### Workflow A — derive an outfit from a WAD

```text
custom.wad
   +
original N-Gage lara.mesh
   ↓
Analyze WAD compatibility
   ↓
Convert WAD
   ↓
new_tpage.tpa
retexture.dat
```

Use this when you have external Lara assets and need the tool to create a new N-Gage atlas/descriptor mapping.

### Workflow B — edit textures without a WAD

```text
existing working N-Gage outfit
new_tpage.tpa + retexture.dat + lara.mesh
   ↓
Export Textures
   ↓
texture_edit.png
   ↓
Photoshop / GIMP / Krita / Paint.NET
   ↓
Import Textures
   ↓
new_tpage.tpa
retexture.dat
```

Use this for repainting an outfit whose N-Gage mapping already works.

### Workflow C — Tomb Editor WAD2

```text
LARA_SKIN.wad2
   +
original N-Gage lara.mesh
   ↓
Analyze WAD2
   ├─ Grade A/B → Convert Compatible Outfit
   └─ Grade C   → Export Geometry Lab
```

A WAD or WAD2 is **optional source material**, not a permanent requirement once a working N-Gage outfit mapping exists.

---

## 3. What the three N-Gage files do

### `new_tpage.tpa`

The actual custom indexed artwork and embedded palettes.

```text
32768 bytes
256×256
4 bits per pixel
```

### `retexture.dat`

The mapping/patch file.

```text
101 descriptor records in bank A
101 descriptor records in bank B
629 face patch records
9006 bytes total
```

### `lara.mesh`

The geometry reference for the retexture system.

It contains 15 main Lara body meshes plus 11 weapon/holster variants.

In the v0.3 texture-only workflows it is **read only**. The tool does not modify it.

---

## 4. Export an editable outfit

### GUI

1. Run `run_gui.bat` on Windows or `./run_gui.sh` on Linux/WSL.
2. Choose **Texture Editor**.
3. Select the current `new_tpage.tpa`.
4. Select its matching `retexture.dat`.
5. Select the original/matching `lara.mesh`.
6. Choose a new workspace folder.
7. Click **Export Editable Texture**.

### CLI

```bash
python3 tr_ngage_outfit.py export-textures new_tpage.tpa \
    --retexture retexture.dat \
    --lara-mesh lara.mesh \
    -o MyOutfitWorkspace
```

---

## 5. Understand the workspace

### `texture_edit.png`

The main editable file. It is a normal 256×256 RGB PNG.

Do not resize it.

### `texture_edit_4x.png`

A 1024×1024 nearest-neighbor preview for easier inspection. Do **not** import this enlarged image; edit/import the 256×256 file.

### `coverage_mask.png`

White shows the descriptor bounding regions that participate in the current outfit mapping. Black is outside the current editable mapping.

For triangle descriptors, part of a rectangular white bounding region can still lie outside the actual triangle. Painting there is harmless but may not appear in-game.

### `palette_group_map.png`

Each distinct color represents one independent 4-bpp palette group. This is a diagnostic map, not Lara artwork.

If two nearby texture islands have different map colors, they are quantized independently.

### `descriptor_layout.csv`

Useful for reverse engineering or troubleshooting. It identifies descriptor index, local texture code, palette group, bounding rectangle and the Lara meshes using that descriptor.

### Template files

```text
template_new_tpage.tpa
template_retexture.dat
palette_map.bin
texture_reference.rgb
workspace.json
```

Do not manually edit these unless you are deliberately modifying the workspace format.

---

## 6. Edit in Photoshop / GIMP / Paint.NET / Krita

Open:

```text
texture_edit.png
```

Keep:

```text
width  = 256
height = 256
```

You may repaint:

```text
shirts
pants
hair
skin
face details
logos
camouflage
tattoos
blood/damage
fabric patterns
shading
```

You may use normal RGB colors and anti-aliasing. The importer handles palette reduction.

Do not globally move the atlas artwork because the UV coordinates in `retexture.dat` stay fixed.

---

## 7. Transparency

Default transparent editing color:

```text
RGB 255,0,255
#FF00FF
```

Inside an active region:

```text
#FF00FF -> palette index 0 -> transparent
```

If you need visible magenta, use a nearby value such as:

```text
250,0,250
```

PNG alpha transparency is also recognized. If the workspace was exported with a custom transparency key, alpha-transparent PNG pixels are converted to that workspace key on import.

---

## 8. Why only 15 visible colors per group?

The page is 4 bpp:

```text
4 bits = 16 indices
```

The tool reserves:

```text
index 0      transparency
indices 1-15 visible colors
```

So each palette group gets at most 15 visible colors.

You do not need to hand-pick them. For example, you can paint a blue shirt with gradients, stitching, shadows and a red logo in full RGB. On import the tool creates the best available 15-color hardware palette for that group and maps the pixels to it.

This is why subtle gradients can become more posterized on the real game.

---

## 9. The magenta-torso example

The reverse-engineering diagnostic modified a torso-focused palette group to bright magenta.

The relevant CLUT rows were:

```text
normal bank A:     VRAM Y 500
alternate bank B:  VRAM Y 436
```

Only the associated Lara clothing polygons changed. That hardware result proved the descriptor -> CLUT -> TPA -> visible polygon relationship used by the editor.

---

## 10. Import the edited image

### GUI

1. Choose the exported workspace.
2. Choose your edited 256×256 PNG/BMP.
3. Choose a new output folder.
4. Select **duplicate** for the first test.
5. Click **Import Edited Texture**.

### CLI

```bash
python3 tr_ngage_outfit.py import-textures MyOutfitWorkspace \
    --image MyOutfitWorkspace/texture_edit.png \
    --alternate-mode duplicate \
    -o MyEditedOutfit
```

Output:

```text
new_tpage.tpa
retexture.dat
imported_preview.png
imported_preview_4x.png
edit_diff_mask.png
import_manifest.json
INSTALL.txt
```

`edit_diff_mask.png` shows which covered RGB pixels changed compared with the exported reference.

---

## 11. Alternate palette modes

### `duplicate` — recommended

```bash
--alternate-mode duplicate
```

The new normal CLUTs are copied into the alternate bank too. This is the safest choice when the outfit colors have changed substantially.

### `preserve` — advanced

```bash
--alternate-mode preserve
```

Only normal palettes are rebuilt. The original alternate bank remains untouched.

This may look wrong if your new normal artwork no longer matches those old alternate palettes.

---

## 12. Install on N-Gage

Back up the originals first.

Copy:

```text
new_tpage.tpa
retexture.dat
```

to:

```text
E:\System\Apps\tombraider\data\deldata\
```

Leave:

```text
lara.mesh
TOMBRAIDER.NAX
```

unchanged for the v0.2 texture-only workflow.

---

## 13. No-edit round trip

If you export and then import `texture_edit.png` without changing any RGB pixels, the importer bypasses palette rebuilding and copies the template files byte-for-byte.

Test:

```bash
python3 tests/selftest_texture_workspace.py \
    new_tpage.tpa retexture.dat lara.mesh
```

Expected:

```text
SELFTEST PASS: editable texture workspace round-trips byte-for-byte with no edits.
```

---

## 14. Example — recolor AoD Lara with no WAD

Start with:

```text
AoD/new_tpage.tpa
AoD/retexture.dat
lara.mesh
```

Export:

```bash
python3 tr_ngage_outfit.py export-textures AoD/new_tpage.tpa \
    --retexture AoD/retexture.dat \
    --lara-mesh lara.mesh \
    -o AoDWorkspace
```

Open `AoDWorkspace/texture_edit.png` and repaint a clothing region blue.

Import:

```bash
python3 tr_ngage_outfit.py import-textures AoDWorkspace \
    --image AoDWorkspace/texture_edit.png \
    --alternate-mode duplicate \
    -o AoDBlue
```

No WAD is used anywhere in that repaint cycle.

---

## 15. Example — beta Lara after the initial WAD conversion

The first time:

```text
TR1 beta .wad
    ↓
convert-wad
    ↓
working N-Gage beta outfit
```

After that:

```text
working beta new_tpage.tpa + retexture.dat
    ↓
export-textures
    ↓
edit PNG repeatedly
    ↓
import-textures
```

The beta WAD no longer needs to be present for each repaint.

---

## 16. When a WAD/model is still needed

No WAD needed for:

```text
recolors
new clothing artwork
hair/skin changes
logos
tattoos
face repainting
camouflage
texture restoration
```

A WAD/WAD2/model source is useful or required for:

```text
new UV layout
moving islands to new atlas positions
new polygons
new geometry
higher-detail Lara meshes
new weapon-specific geometry
```

---

## 17. Classic WAD converter

Analyze:

```bash
python3 tr_ngage_outfit.py analyze-wad outfit.wad --lara-mesh lara.mesh
```

Convert:

```bash
python3 tr_ngage_outfit.py convert-wad outfit.wad \
    --lara-mesh lara.mesh \
    -o ConvertedOutfit
```

Classic WAD mode supports file ID 129. WAD2 is now a separate v0.3 path under **WAD2 Lab**.

The classic converter and the WAD2 converter both refuse poor topology matches instead of producing obviously unsafe output.

### WAD2

Analyze:

```bash
python3 tr_ngage_outfit.py analyze-wad2 outfit.wad2 --lara-mesh lara.mesh
```

Grade A/B conversions:

```bash
python3 tr_ngage_outfit.py convert-wad2 outfit.wad2 --lara-mesh lara.mesh -o ConvertedOutfit
```

Grade C geometry development:

```bash
python3 tr_ngage_outfit.py export-wad2-model outfit.wad2 --lara-mesh lara.mesh -o GeometryLab
```

See `WAD2-GUIDE.md` and `WAD2-GEOMETRY-LAB.md`.

---

## 18. Troubleshooting

### "Edited texture must remain 256x256"

Your editor changed the canvas size. Restore it to 256×256.

### "Workspace template/hash validation failed"

One of the template/map/reference files changed. Export a fresh workspace or restore the original workspace support files.

### "overlapping descriptors using palette groups ..."

The outfit has overlapping editable regions that use different CLUT groups. v0.2 intentionally refuses this because a single flat RGB pixel cannot safely represent two different palettes at once.

### Colors look simplified

Expected to some degree: each group has only 15 visible hardware colors.

### Alternate state has wrong colors

Reimport with:

```text
--alternate-mode duplicate
```

### Changes do not appear

Check `coverage_mask.png` and `palette_group_map.png`. Pixels outside the current descriptor mapping are not sampled by Lara.

---

## 19. Current roadmap

The detailed roadmap now lives in `PROJECT-ROADMAP.md`. The next major branch is an experimental WAD/WAD2 → N-Gage geometry serializer plus a runtime strategy for using custom geometry on normal levels. Texture-only workflows remain executable-patch-free.


---

## 18. Body/accessory diagnostic examples

v0.2.1 includes two in-game examples under `examples/`. They are not ordinary skins; they are intentionally exaggerated mapping tests designed to show where Lara's body ends and accessories begin.

### Example 1: Arm / Body Contrast

The torso/top and leg/pants faces reuse Lara's arm/skin descriptor while the entire pelvis is left untouched. The resulting green shorts demonstrate that changing the surrounding body is not enough to isolate the belt when the pelvis is treated as a single object-level selection.

### Example 2: Pants + Belt Isolation

The pelvis is still one mesh object, but the tool changes selected pelvis faces independently. The main shorts/pants faces use the arm/skin descriptor while the upper waistband/belt faces keep their original mapping. The in-game result clearly preserves the dark belt.

This is the editor model we should use going forward:

```text
mesh object
   -> face groups
      -> texture descriptors / UVs
         -> editable atlas pixels / palette groups
```

A mesh is therefore **not** the same thing as one editable texture/material. When two regions can be separated by face/descriptor mapping, the editor should expose those face groups. When they genuinely share the same atlas pixels or palette group, the texture itself must be edited or the descriptor layout must be split.

For screenshots, exact face lists, install files, and reproduction commands, see:

```text
docs/BODY-ACCESSORY-SEPARATION.md
examples/01_arm_body_contrast/
examples/02_pants_belt_isolation/
```

The GUI now has an **Examples** tab that can regenerate both diagnostic packages from the exact stock AoD reference files.
