# October repo map

This repository is the single source for the assembled PubCast / PubPartner / Foresight / 2i / CARE program and the Foresight Counter work. Created 2026-10-13.

Where things are
- Root: the merged program (Pete Provider-First base plus the SmolLM branch plus this session's work). Entry point: run_reach.py. Read CONSOLIDATION_PLAN_2026-10-13.md first for the fork analysis and the CARE options.
- static/foresight.html: the running Foresight page (older CPU-drawn look). static/foresight_shapes.js and static/foresight_gl.js: the new tray geometry engine and WebGL2 renderer, built and tested in the lab but not yet wired into foresight.html.
- foresight/lab/: the lab page and Playwright screenshot scripts used to test the new look.
- foresight/research/: five research notes and the report "Hyperreal WebGL tray rendering". Most formulas were written from memory (sources could not be opened); each claim is labeled verified / recalled / derived / estimate.
- skills/: the two saved skills (foresight-tray-art, hyperreal-webgl-rendering).
- docs/handoff/: the 2026-10-13 handoff. Start there in a new session.
- tools/dev/: scripts to start the local test server and run tests file by file (repo-relative; set PYTHON to pick an interpreter).

Not in this repo: the 1.06 GB SmolLM2 model and llama.cpp runtimes (separate download with checksum), and any private data.
Nothing here has been run against a real AI model.
