# Open 2i without Codespaces or usage minutes

This is a **single-file offline preview of the real 2i Writer's Room**. It was generated from `2i/writers-room-v22.html` on the Claude-functional-integration branch, with its 3 CSS files and 13 JS files embedded in place. All 15 classic script blocks parsed successfully in a syntax check. A full Windows browser run has **not** been verified.

## Download and open

1. Open [2i/preview-standalone.html](2i/preview-standalone.html) in GitHub.
2. In the GitHub file viewer, click **Download raw file** (the download/down-arrow icon). It should save `preview-standalone.html` to your Downloads folder.
3. Double-click the downloaded .html file to open it in your browser. Keep the `file://` address. **Do not open it through a web HTML preview service**: the app uses a deliberately offline path when opened as a file.
4. Try the notebook and writing controls with disposable demo text. To keep anything important, use **Save a copy** or **Export** to download a .2i or Markdown manuscript. Browser recovery is not a backup.

## What is and isn't included

This is **real 2i editor code and original styling**, not a visual mockup or a replacement application. The self-contained file includes local JavaScript/CSS imports only. It does **not** include the PubCast server, Reach account database, Node sidecar, cloud AI, collaborative service, model provider, or server-hosted Save Now.

Expect server-backed functions to be unavailable and possibly show offline errors. The standalone file is for interacting with the UI and local editor functions. The **full actual system** still runs through `python run_reach.py --start-page writers-room` with its Python dependencies. This preview must not be used as the sole repository of important work.

## Branch safety

Only `preview/2i-live-2026-11-17` contains the bundled preview and helper launch files. No changes were made to `main` or the existing 2i/Claude integration branches.
