# WAD2 coverage, fallback meshes, and the Gold Lara lesson

The first v0.3.0 WAD2 conversion of `TR1_Lara_Gold.wad2` was an important hardware/emulator test because it revealed the difference between **primary Lara topology coverage** and **actual runtime outfit coverage**.

## What v0.3.0 did

Object 12 (`LARA_SKIN`) matched 335 of the N-Gage primary Lara's 375 faces. The converter assigned the WAD2 Gold texture to those 335 faces and used `0xFFFF` Classic fallback on the 40 topology-mismatched primary faces.

It also deliberately left all 254 faces in the 11 extra N-Gage weapon/holster mesh records on Classic fallback.

The result rendered and proved that WAD2 texture conversion worked, but screenshots showed several non-gold regions:

- portions of the head/hair;
- small torso regions;
- tan upper thigh/holster regions.

The patch report explained these precisely:

```text
head:  53 WAD2 + 32 Classic fallback
torso: 24 WAD2 + 8 Classic fallback
weapon/holster variants: 254 Classic fallback
```

The normal left/right thigh meshes were already completely WAD2-mapped. Therefore the remaining tan upper-thigh regions demonstrate that Tomb Raider swaps in the separate pistol/holster thigh variants (`extra_01_01` and `extra_01_04`) during ordinary gameplay. This is direct runtime evidence that a polished outfit converter must account for all 26 `lara.mesh` records, not merely the first 15 body meshes.

## Why Gold Lara can be completed safely

The selected `LARA_SKIN` in `TR1_Lara_Gold.wad2` uses only texture 0. That texture is 4x4 BGRA and all 16 texels are the same fully opaque RGB color `(252,236,136)`.

For a uniform source texture, face-specific UVs are irrelevant: every sample returns the same color. Therefore topology-mismatched faces and extra weapon meshes can safely reuse one valid Gold descriptor while retaining the N-Gage face vertex order.

v0.3.1 adds WAD2 fallback modes:

- `auto` — default; complete unmatched faces only when all used source textures are fully opaque and collapse to one PSX BGR555 color;
- `classic` — retain the v0.3.0 behavior and leave unmatched faces on `0xFFFF` Classic fallback;
- `uniform` — require a uniform source and explicitly force full completion.

For Gold Lara, `auto` produces:

```text
Primary faces:        375 / 375 custom
Extra weapon faces:   254 / 254 custom
Total:                629 / 629 custom
Classic fallbacks:      0
```

This rule is intentionally narrow. A normal textured WAD2 outfit cannot use this shortcut because unmatched polygons need meaningful source UV/material information or actual geometry conversion.
