# Included diagnostic examples

The public package omits the two unchanged stock AoD texture pages. Keep or restore your own `new_tpage.tpa` (SHA-256 `0c0f7a8fb1ccd43d45a088b4c589e6135b396823a5fe8ef8ffada962fe829daa`) and install only the supplied modified `retexture.dat`. The Examples tab can regenerate both files from your original inputs.

These two example sets are the in-game tests used to design the first body/accessory face groups for the editor.

## 01 — Arm / Body Contrast

```text
examples/01_arm_body_contrast/
```

Maps torso/top and thigh/calf pants faces to the same arm/skin descriptor but leaves the pelvis untouched.

Observed result: the body becomes visually uniform, but the original pelvis shorts remain and make the belt difficult to isolate.

Included modified file (use your own stock AoD texture page):

```text
INSTALL/retexture.dat
```

Generated retexture SHA-256:

```text
f3865542fba51817dea740db19715d445dfa7c6a2e30b6d67c931b923909a2d2
```

## 02 — Pants + Belt Isolation

```text
examples/02_pants_belt_isolation/
```

Keeps the same body treatment, then separates the pelvis at face/descriptor level: main shorts/pants faces are remapped to arm/skin while upper waistband/belt faces preserve their original descriptors.

Observed result: the dark belt remains clearly visible against the skin-toned pelvis and legs.

Generated retexture SHA-256:

```text
89dcf58f119a8bf848bf8a964221f600982e23808a5039d1339fae06e2557965
```

## Technical correction that matters for future editing

The pelvis is **one mesh object**, but the belt and shorts are not forced to be one texture/material. The successful second test separated them using individual face/descriptor assignments without changing the mesh geometry.

If a different custom outfit stores the belt and shorts in the same actual atlas pixels or palette group, then face reassignment alone is insufficient: those pixels/descriptors have to be edited or split.

See `../docs/BODY-ACCESSORY-SEPARATION.md` for the full explanation and screenshots.

## WAD2 compatibility reports (v0.3)

`wad2_compatibility_reports/` contains derived JSON reports from the development WAD2 samples. Source WAD2 assets are not bundled in the main tool package.

They demonstrate the new compatibility grading:

- TR1 Lara Gold: Grade A / direct texture-topology conversion candidate.
- TR5 Lara Skeleton: Grade C / geometry-replacement branch.
- TEN Lara: Grade C / animation-skeleton object rather than a compatible skin.

## Screenshot naming convention

Example screenshots intentionally use orientation-neutral names such as `image_01.jpg`, `image_02.jpg`, etc. Do not name screenshots `front`, `rear`, `side`, or similar unless the view has been independently verified. This avoids attaching incorrect view labels to emulator/hardware captures.
