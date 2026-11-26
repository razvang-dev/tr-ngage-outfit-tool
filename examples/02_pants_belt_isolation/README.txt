TR N-Gage Outfit Tool v0.2.1 — Arm-Body + Pelvis Pants / Belt Isolation Test

PURPOSE
-------
This is the follow-up to the successful arm/body contrast test. The previous build left the entire pelvis mesh untouched, which is why the green shorts remained visible and obscured the belt separation.

The pelvis is ONE mesh, but its faces can still be reassigned independently. This build maps the lower/main pelvis shorts faces to the same arm/skin descriptor (local code 18) while preserving the upper waist-band/belt faces on their original descriptors.

CHANGED
-------
- torso/top body faces -> arm/skin descriptor
- left/right thigh -> arm/skin descriptor
- left/right knee/calf -> arm/skin descriptor
- pelvis/shorts faces 0-5, 8, 10-15, 18-21 -> arm/skin descriptor

PRESERVED
---------
- pelvis upper waist/belt band faces 6, 7, 9, 16, 17, 22, 23
- backpack mappings
- boots / feet
- hands
- head / hair
- weapon / holster variant meshes

IMPORTANT LIMITATION
--------------------
The belt and shorts are not separate mesh objects. Some side polygons span a large vertical part of the pelvis, so this test preserves the discrete upper-band faces while remapping the main shorts body. If a small side section of the belt disappears, that tells us the belt is baked into one of those spanning pelvis polygons and the next version should split/remap that polygon or create a two-tone custom descriptor.

Total changed face records: 93

HARDWARE TEST
-------------
Back up your originals first. Copy ONLY:

  INSTALL\retexture.dat

to:

  E:\System\Apps\tombraider\data\deldata\

Keep your own stock AoD new_tpage.tpa in the target directory. It is not bundled in the public package. The required SHA-256 is
0c0f7a8fb1ccd43d45a088b4c589e6135b396823a5fe8ef8ffada962fe829daa.
If needed, restore it from your own backup or regenerate the example with the Examples GUI tab. The visible change comes entirely from retexture.dat face assignments. Leave lara.mesh unchanged.

Please test front, rear, and side views. The key area is the black/dark waistband against the now skin-colored pelvis and legs.

MESH EXPORT
-----------
mesh_export\lara_primary15_arm_body_pants_belt.obj
  - updated assembled 15-part Lara OBJ
  - remapped pelvis/pants/top faces point to the arm skin texel
  - preserved upper belt faces retain their original UV descriptors

mesh_export\parts\00_pelvis.obj
  - especially useful for inspecting which pelvis faces remain belt-textured
