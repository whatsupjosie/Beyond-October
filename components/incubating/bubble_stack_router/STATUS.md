# Bubble Stack Router Status

The real deformation, scene-contract, and streaming-chain modules are installed
under `modules/` and are eligible for contract testing.

The consolidation router is intentionally **not** installed as a live module and
is not mounted in `main.py`: its `/impact` endpoint uses `Scene.demo_scene()`.
That is useful regression/demo behavior, but not a production scene-authority
integration.

Promotion gate: build the scene from current PubWorld/room authority, execute
impact + regression + startup tests, then mount the router.
