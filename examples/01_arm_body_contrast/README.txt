TR N-Gage Outfit Tool v0.2.1 — Arm-Body Contrast Test

PURPOSE
-------
This diagnostic maps Lara's shirt/top and leg/pants faces to the SAME N-Gage texture descriptor already used by her arms (local texture code 18).

The arm descriptor is a one-texel skin sample at UV (240,26), so the remapped body areas should become a consistent flat skin tone. This is intentional: it creates a strong visual/3D separation between the body and accessories for later editing.

PRESERVED ON PURPOSE
--------------------
- backpack mapping
- pelvis / belt / waist-accessory mapping
- boots / feet
- hands
- head / hair
- weapon / holster variant meshes

CHANGED
-------
- left/right thigh: all faces -> arm texture
- left/right knee/calf: all faces -> arm texture
- torso/body/top texture codes 1, 35, 36, 37, 39–46 -> arm texture; backpack/accessory codes 38 and 47–52 stay original

Total changed face records: 76

HARDWARE TEST
-------------
Back up your originals first. Copy ONLY:

  INSTALL\retexture.dat

to:

  E:\System\Apps\tombraider\data\deldata\

Keep your own stock AoD new_tpage.tpa in the target directory. It is not bundled in the public package. The required SHA-256 is
0c0f7a8fb1ccd43d45a088b4c589e6135b396823a5fe8ef8ffada962fe829daa.
If needed, restore it from your own backup or regenerate the example with the Examples GUI tab. The test is driven by the modified retexture.dat face assignments. Leave lara.mesh unchanged.

Test an early/normal level first.

MESH EXPORT
-----------
mesh_export\lara_primary15_arm_body_contrast.obj
  - assembled 15-part Lara bind-pose OBJ
  - Y converted to normal Y-up OBJ convention
  - custom N-Gage UVs included where retexture.dat supplies them
  - remapped top/pants faces point to the same arm texel

mesh_export\parts\
  - each of the 15 primary Lara meshes as a separate local-space OBJ

mesh_export\texture_edit.png
  - editable N-Gage texture atlas used by the OBJ material

Faces using the game's Classic fallback have geometry but no custom UV coordinates and are assigned Classic_Fallback material.
