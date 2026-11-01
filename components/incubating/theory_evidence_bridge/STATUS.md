# Theory/Evidence Bridge Status

Preserved from the 2026-09-03 consolidation package for engineering review.

The underlying `modules/theory_graph.py`, `modules/evidence_layer.py`, and
`modules/contradiction_engine.py` already match this package byte-for-byte.

This bridge is intentionally **not installed into `modules/` and not wired into
EVO runtime** because its source explicitly documents newly invented instability
weights and says it was not executed inside live `evo_integration.py`.

Promotion gate: review the weighting policy, integrate against the actual current
EVO contract, and execute focused + regression tests before moving this into the
live module namespace.
