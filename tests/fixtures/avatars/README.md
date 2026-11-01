# Avatar import test files

Real, rigged models used by `tests/test_avatar_import_browser.py` and `tests/test_avatar_imports.py`.

| File | What it tests | Source | License |
|---|---|---|---|
| `mh_male.glb`, `mh_female.glb` | GLB with a 52-bone Mixamo-standard skeleton and a "Wave" animation | MakeHuman base mesh via MPFB 2 (github.com/makehumancommunity/mpfb2), built by `build/build_test_humans.py` | CC0 1.0 |
| `mh_male.fbx` | FBX in metres, skeleton and animation | same | CC0 1.0 |
| `mh_female.fbx` | FBX exported at ×100 (centimetre units): the classic "giant import" | same | CC0 1.0 |
| `mh_male.obj` + `.mtl` | OBJ, Y-up. OBJ cannot store a skeleton, so it imports as a standing figure | same | CC0 1.0 |
| `mh_female.obj` + `.mtl` | OBJ written Z-up, so it arrives lying on its back | same | CC0 1.0 |
| `husky.glb` | Four-legged animal skeleton (49 bones, 12 animations), raw file 3.2 m tall | Quaternius, Ultimate Animated Animal Pack (quaternius.com/packs/ultimateanimatedanimals.html), copy from github.com/trebeljahr/quaternius-showcase `public/glb/animals_pack/Husky.glb` | CC0 1.0 |

The MakeHuman figures are generated, unclothed base bodies with a single-colour skin material.
Regenerate with headless Blender (`pip install bpy`) and an MPFB 2 checkout next to the script:
`python build/build_test_humans.py OUTPUT_DIR`.
