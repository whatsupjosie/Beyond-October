# Large and binary file inventory - integration/converge-2026-11-20

Written 2026-11-20, so you can decide what the new repository should actually hold.
Nothing here has been removed. This is a list, not a recommendation to delete.

Tracked files: 2518
Tracked content: 135.72 MB

## Every file of one MB or more

| Size | Path | First added (commit, date, author) |
|------|------|-----------------------------------|
| 9.24 MB | `bin/ws_renderer` | `104e502` 2026-11-01 Claude |
| 6.17 MB | `recovery/2026-10-21/avatars/retrieved/avatar_catalog/animation--walking-with-skin-glb.zip` | `104e502` 2026-11-01 Claude |
| 3.83 MB | `recovery/2026-10-21/avatars/retrieved/avatar_catalog/animation__walking_with_skin_glb.glb` | `104e502` 2026-11-01 Claude |
| 3.78 MB | `2i/2i-assets/vendor/docx/engine.js` | `d993d26` 2026-11-18 Claude |
| 3.72 MB | `recovery/2026-10-21/avatars/retrieved/avatar_extra/Lena_Reconstruction_Executable_Experiment.zip` | `104e502` 2026-11-01 Claude |
| 2.79 MB | `static/world/test_avatars/Xbot.glb` | `104e502` 2026-11-01 Claude |
| 2.40 MB | `static/world/rooms/manager_office_painting.png` | `6280693` 2026-11-02 Claude |
| 2.35 MB | `assets/avatar/cast/pete/reference/pink_haired_biker_character_sheet.png` | `104e502` 2026-11-01 Claude |
| 2.32 MB | `assets/avatar/cast/pete/reference/alex_character_reference_sheet.png` | `104e502` 2026-11-01 Claude |
| 2.22 MB | `recovery/2026-10-21/avatars/retrieved/avatar_catalog/Reaching reach/PubWorld_Golden_Avatar.png` | `104e502` 2026-11-01 Claude |
| 2.22 MB | `recovery/2026-10-21/avatars/retrieved/avatar_catalog/PubWorld_Golden_Avatar.png` | `104e502` 2026-11-01 Claude |
| 2.19 MB | `recovery/2026-10-21/avatars/retrieved/avatar_catalog/standard_walk.glb` | `104e502` 2026-11-01 Claude |
| 2.19 MB | `assets/avatar/cast/pete/reference/alex_modular_character_parts_sheet.png` | `104e502` 2026-11-01 Claude |
| 2.05 MB | `assets/avatar/cast/pete/reference/pink_haired_biker_jacket_turnaround_sheet.png` | `104e502` 2026-11-01 Claude |
| 2.04 MB | `recovery/2026-10-21/avatars/retrieved/avatar_catalog/Reaching reach/Neon Spirit Orb Avatar.png` | `104e502` 2026-11-01 Claude |
| 1.93 MB | `assets/avatar/cast/pete/reference/alex_walk_cycle_reference_sheet.png` | `104e502` 2026-11-01 Claude |
| 1.85 MB | `recovery/2026-10-21/menus/retrieved/pubcast_core_menu/PubCast_Menu_Work_GitHub_Recovery_2026-10-18.zip` | `104e502` 2026-11-01 Claude |
| 1.83 MB | `tests/fixtures/avatars/mh_female.obj` | `104e502` 2026-11-01 Claude |
| 1.81 MB | `tests/fixtures/avatars/mh_male.obj` | `104e502` 2026-11-01 Claude |
| 1.70 MB | `static/director_console_overlay_map.png` | `104e502` 2026-11-01 Claude |
| 1.70 MB | `static/director_console.png` | `104e502` 2026-11-01 Claude |
| 1.62 MB | `static/audio_console_overlay_map.png` | `104e502` 2026-11-01 Claude |
| 1.61 MB | `recovery/2026-10-21/avatars/retrieved/avatar_extra/Lena_Official_TRELLIS_Multiview_Integration.zip` | `104e502` 2026-11-01 Claude |
| 1.46 MB | `handoffs/screens_2026-10-14/counter_page_six_programs.png` | `104e502` 2026-11-01 Claude |
| 1.45 MB | `handoffs/screens_2026-10-14/lab_after_reload.png` | `104e502` 2026-11-01 Claude |
| 1.45 MB | `handoffs/screens_2026-10-14/counter_page_after_reload.png` | `104e502` 2026-11-01 Claude |
| 1.37 MB | `handoffs/screens_2026-10-14/counter_page_file_menu.png` | `104e502` 2026-11-01 Claude |
| 1.25 MB | `handoffs/screens_2026-10-14/counter_page_picker.png` | `104e502` 2026-11-01 Claude |
| 1.21 MB | `static/vendor/three-0.160.0/build/three.module.js` | `104e502` 2026-11-01 Claude |
| 1.19 MB | `tests/fixtures/avatars/mh_female.fbx` | `104e502` 2026-11-01 Claude |
| 1.19 MB | `tests/fixtures/avatars/mh_male.fbx` | `104e502` 2026-11-01 Claude |
| 1.10 MB | `static/world/rooms/vortex_bar.jpg` | `104e502` 2026-11-01 Claude |
| 1.10 MB | `recovery/2026-10-21/avatars/retrieved/avatar_catalog/Lena_Hart_Reference_Volume_STATIC.glb` | `104e502` 2026-11-01 Claude |

Subtotal for these 33 files: 76.35 MB (56 percent of tracked content)

## Binary weight by directory

| Directory | Binary bytes | Files |
|-----------|-------------|-------|
| `recovery` | 34.17 MB | 41 |
| `static` | 24.74 MB | 71 |
| `assets` | 11.62 MB | 8 |
| `bin` | 9.24 MB | 1 |
| `tests` | 8.55 MB | 18 |
| `handoffs` | 7.01 MB | 6 |
| `2i` | 5.76 MB | 14 |
| `docs` | 2.33 MB | 14 |
| `foresight` | 0.11 MB | 1 |
| `run3_bridge` | 0.01 MB | 1 |

Binary total: 103.55 MB in 175 files, 76 percent of tracked content.

## Things worth a decision

These are observations, not actions taken:

- `bin/ws_renderer` is 9.23 MB here. `codex/main-debug-20261119` rebuilds the same
  binary at 1.81 MB. If that branch lands, the file shrinks by about 7.4 MB. It is a
  compiled artifact of `rust_crate/src/ws_renderer.rs`, which is also in the tree, so
  it can be rebuilt rather than stored.
- `recovery/2026-10-21/` holds about 20 MB of retrieved avatar archives and `.zip`
  files, including zips that also exist unpacked beside them. It is recovery material,
  not running code.
- `2i/2i-assets/vendor/docx/` holds the 3.77 MB minified DOCX engine plus 5.19 MB of
  Carlito and Liberation fonts and `harfbuzz.wasm`. These are vendored on purpose for
  offline DOCX export and carry a `PROVENANCE.json`.
- `handoffs/screens_2026-10-14/` holds about 7 MB of PNG screenshots used as evidence
  in old handoffs.
- `tests/fixtures/avatars/` holds about 6 MB of `.obj` and `.fbx` fixtures that the
  avatar tests load.
- Two files under `recovery/2026-10-21/avatars/retrieved/avatar_catalog/Reaching reach/`
  have a space in the directory name, which is why git could not resolve their adding
  commit in a single query. They are 2.14 MB and 2.22 MB PNGs.

