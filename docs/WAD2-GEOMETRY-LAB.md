# WAD2 Geometry Lab — v0.4

The geometry branch exists because texture conversion and geometry conversion are fundamentally different problems.

A Grade-C WAD2 can have the correct Lara skeleton/body-part semantics while using completely different mesh topology. `TR5_Lara_Skeleton.wad2` is the current development example.

## Two geometry tools now exist

### 1. Export Geometry Lab

```bash
python tr_ngage_outfit.py export-wad2-model source.wad2 \
    --lara-mesh lara.mesh \
    -o geometry_lab
```

This exports the 15 WAD2 body parts as OBJ files plus their source textures and Bone2 metadata. It is useful for Blender/manual study and makes no game-format changes.

### 2. Build EXP Geometry

New in v0.4:

```bash
python tr_ngage_outfit.py build-wad2-geometry source.wad2 \
    --lara-mesh lara.mesh \
    -o geometry_bundle
```

This is a real serializer. It writes:

```text
lara.mesh
new_tpage.tpa
retexture.dat
```

whose face topology, UV descriptors, palettes and patch stream all correspond to the source WAD2 model.

See `GEOMETRY-SERIALIZER.md` for the binary details and runtime warning.

## Current status

### Solved in v0.4

- WAD2 positions → N-Gage signed-16 mesh positions;
- WAD2 fixed-point normals / computed-normal fallback;
- WAD2 sphere bounds → N-Gage record bounds;
- arbitrary source quad/triangle topology;
- direct WAD2 UV mapping instead of topology matching;
- matching dynamic-length retexture face stream;
- 26-record output, including synthesized variant records;
- exact parser round-trip validation.

### Still unsolved

The stock executable does not use external `lara.mesh` in every normal level. A generated geometry bundle therefore is not yet a safe game-wide install.

The next task is **runtime mesh activation** in `TOMBRAIDER.NAX`: extend the already-understood outfit/retexture path so ordinary levels use the custom external geometry and the custom face stream together.

After that:

1. test TR5 geometry in ordinary levels;
2. build real pistol/magnum/Uzi/shotgun variant meshes rather than primary-body clones;
3. add geometry to the normal one-click installer;
4. add Blender/project authoring helpers.
