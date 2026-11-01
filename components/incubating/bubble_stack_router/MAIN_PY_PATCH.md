# Wiring Bubble Stack into main.py

## 1. File placement

Copy these into your real repo exactly as laid out here:

```
modules/bubble_stack_pikpc/__init__.py
modules/bubble_stack_pikpc/core.py
modules/bubble_stack_pikpc/engine.py
modules/bubble_stack_pikpc/performance.py
modules/bubble_stack_pikpc/sandbox.py
modules/scene_contract.py
modules/streaming_chain_resolver.py
modules/deformation_math.py
modules/voxel_set_contract.py
modules/bubble_stack_routes.py   <- new, adapts routes.py to your router pattern
```

`bubble_stack_pikpc/routes.py` (the original, standalone-FastAPI-app version)
is NOT copied — `modules/bubble_stack_routes.py` replaces it with the same
three endpoints as a mountable router, plus a new `/impact` endpoint wiring
the physics chain.

## 2. Add to main.py's optional-import block

Find this block (same place as `_HAS_EVO`, `_HAS_CHOREO`, etc.):

```python
_HAS_CRICKET          = False
_HAS_THINKING_CONTEXT = False
...
_HAS_DOCTOR           = False
```

Add one line to that list:

```python
_HAS_BUBBLE_STACK     = False
```

Then add a new guarded import alongside the others (same pattern as
`_HAS_CHOREO`):

```python
try:
    from modules.bubble_stack_pikpc.core import BubbleConfig
    from modules.bubble_stack_pikpc.engine import BubbleStackEngine
    from modules.bubble_stack_routes import create_bubble_stack_router
    _HAS_BUBBLE_STACK = True
except ImportError:
    BubbleConfig            = None
    BubbleStackEngine       = None
    create_bubble_stack_router = None
```

## 3. Boot step — create the engine instance

Wherever `main.py` constructs the other optional systems (near where
`ChoreographyController`/`LightingEngine` get instantiated — this repo's
own comment calls that pattern boot steps 2b/2c/2d), add:

```python
bubble_stack_engine = None
if _HAS_BUBBLE_STACK:
    bubble_stack_engine = BubbleStackEngine(BubbleConfig())
    logger.info("[BubbleStack] Engine initialized")
```

## 4. Mount the router

Wherever the other routers get included (same place as
`app.include_router(create_production_router(...))`,
`app.include_router(create_governance_router(...))`):

```python
if _HAS_BUBBLE_STACK and bubble_stack_engine is not None:
    app.include_router(create_bubble_stack_router(bubble_stack_engine))
```

## 5. Health check (optional, matches existing pattern)

If `main.py`'s `/health` endpoint reports on other optional systems the
same way it does for choreo/lighting/evo, add:

```python
"bubble_stack": _HAS_BUBBLE_STACK,
```

## What you get

- `POST /api/bubble-stack/frame` — spatial-attention frame ingest (existing
  BubbleStackEngine behavior, unchanged from the original routes.py)
- `GET /api/bubble-stack/summary` — Jeremy room summary
- `GET /api/bubble-stack/query?x=&y=&z=` — point query
- `POST /api/bubble-stack/impact` — NEW. Triggers a real physics impact
  chain (mass, impulse, material deformation, secondary-contact
  propagation) between two objects. Currently runs against
  `Scene.demo_scene()` (the 5-object cup/vase/table/chair/actor set) —
  swap that for a real scene-authority hookup when one exists; the
  resolver and router don't need to change, per scene_contract.py's own
  integration contract.

## Verified before delivery, not just written

Both the base three endpoints and the new `/impact` endpoint were run
end-to-end against a live FastAPI TestClient in this session — real HTTP
requests, real responses. The impact test (77.1 kg actor, 8 m/s into the
cup) returned `initial_energy_joules: 2467.2`, matching the exact figure
`streaming_chain_resolver.py`'s own regression-test comment cites for that
scenario. The chain propagated correctly, launch velocity and rebound
velocity both computed, mass-budgeted energy consumed to zero.

## Known open item, unchanged by this patch

`/impact` runs against the hardcoded demo scene, not your real
production scene state. Swapping `Scene.demo_scene()` for a real scene
built from live PubWorld/room state is the next real step — this patch
wires the pipe, it doesn't yet connect the other end.
