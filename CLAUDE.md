# Build integration protocol (all AI and human collaborators)

Read `STATUS.md` before any modifications. This is a single Foresight/Reach
Build; `static/foresight_counter.html` is the Counter entry and
`static/foresight_counter.js` owns tray physics. `static/foresight_programs.js`
provides content. `main.py` and `run_reach.py` own the local authenticated host
and launcher. `2i/writers-room-v22.html` owns 2i editing/chat, not the tray.

**Do not** overlay an old Prime/Horizon/NowCurtsey donor on top of the newer
Counter or communications runtime. Those repositories are for targeted reuse
with provenance and regression testing. Do not rewrite Josie's text, layouts,
identity metadata, or design choices. Avoid stubs and fabricated pass claims.

Do not auto-install optional browser, GPU, model or Node dependencies on app
startup. Core operation is offline-first. Treat `data/secure`, `data/users.db`,
private accounts, vaults and Blackbox recordings as runtime data, not code.
Never place them in public artifacts. The canonical PubPartner Alex vessel is
not interchangeable with a recovered donor. Preserve its SHA-1 Git blob ID
`96fa66a728d07d5ff43b0d3d7fc17a466765cec1`.

Each change needs: reason, exact paths, source provenance, targeted tests,
regression checks, and a clear tested/untested ledger. Preserve the previous
version before editing. Windows commands must work with PowerShell 5.

Next goal: **fully commission the Foresight Counter inside Build**, not
implement disconnected features in another repository. Verify real launch,
menus, five distinct tray sizes, 2i hosting, file open/save/reopen, rollback on
failed write, quit and restart, graphics compatibility mode, and actual UI
behavior. Don't count a route as a working service or a DOM mock as production.
