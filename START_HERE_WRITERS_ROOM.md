# Reach — your Writer’s Room

This candidate uses **your original Writer’s Room picture** as the visible shell. Transparent buttons sit over the buttons in the picture. Your editable manuscript, references, conversation, and current status cover the sample text printed in the picture.

**Startup update:** this download includes the revised launcher. It checks several Python commands, verifies the dependencies, retries an interrupted installation, and keeps errors visible. After Python starts, diagnostic output is saved to `reach-startup.log` beside the launcher.

## Open it

1. Extract the ZIP into its own folder. Keep it separate from a newer Reach installation.
2. On Windows, double-click **OPEN_REACH_WINDOWS.bat**. Python 3.11 or newer must already be installed; the first launch downloads the Python dependencies. Python 3.12 was used for the checks.
3. On macOS or Linux, run **bash open_reach.sh** from the extracted folder.
4. The browser opens the Writer’s Room. Create your local account on the first visit. Keep the terminal open while using Reach.

If it fails, send a screenshot of the error window or the last error lines from `reach-startup.log`. If it says the folder is incomplete, use **Extract All** on the ZIP before opening the launcher. If it cannot find Python, it will say so directly.

If port 8000 is occupied, run `.reach-venv/Scripts/python.exe run_reach.py --port 8001` on Windows, or `bash open_reach.sh --port 8001` on macOS/Linux.

Your new work goes into **reach_userdata/** beside the launcher. Preserve that whole folder, including its account and key files, when moving or backing up this installation. Opening `2i/index.html` directly does not start Reach or load the button map.

## Phone edition

The same build now includes a separate phone layout. Open **Menu → Phone view** to try it on your computer. Screens up to 600 CSS pixels wide choose it on their first visit; an explicit layout choice takes precedence. You can also open `http://127.0.0.1:8000/writers-room?view=phone` on the computer running Reach. Adjust the port if needed.

The phone view has **Write**, **Partner**, and **Archive** tabs, 48-pixel minimum button targets, readable manuscript text, and the original artwork as its notebook and brass framing. **Whole desk picture** returns to the desktop artwork without reloading or discarding your draft. Both views use the same editor and document APIs. On a second device, sign in to the same Reach account and use **My manuscripts** to open an existing saved document.

**A ZIP or a phone layout does not make the Python server run on a phone.** The supplied launcher listens only on the computer itself. An actual phone needs a reachable, authenticated Reach address; that connection has not been set up or verified by this update. Do not type `127.0.0.1` into the phone expecting it to reach your computer. See `PHONE_EDITION.md` for the precise scope and checks.

## Audio, menu and window controls

The phone top bar now exposes **☰ Menu**, **⚙ Settings**, **— Shrink** and **× Close view**. Reopen restores a closed desk. Settings includes phone text size, audio options and PubPartner connection settings. The audio panel reads existing text with start/play/pause/stop, paragraph jumps, ten-word skips, voice, speed and volume controls. It reports unsupported or blocked speech. The chosen phone/browser voice is separate from a live PubPartner voice.

The current revision passed 16 integrated editor groups, 3 reader logic groups, and 8 standalone/inline groups, plus the real HTTP bootstrap/save/restart probe. These are control and state tests; actual handset audio/rendering is unverified.

## Use your room

- Write on the notebook page. **Save** and automatic saving keep the manuscript in Reach; a browser recovery copy is also kept. Wait for “Saved to Reach” before closing.
- The **menu** in the top right contains **My manuscripts**, import, export, rename, draft commit, and actual-size/fit controls. **Show clickable areas** outlines every pictured button on the unchanged artwork.
- **New scene** adds a chapter boundary. The bottom arrows and **Outline** jump among scenes within the manuscript. Click the heading on the page to rename the scene.
- **Lock scene** protects its existing lines. **Insert** puts your partner’s latest reply in a draft area for review. **Menu → Commit draft** adds it to the manuscript.
- The archive holds your references. Its pictured search icon and all four archive tabs are clickable. **Characters**, **Worldbuilding**, and **Notes** open their collections. The **+** beside Scene Ideas adds an idea.
- Choose the partner at the top of the conversation. The gear opens their model settings. This room uses the integrated PubPartner host and its existing system bridge.
- If two windows change the same saved revision, Reach keeps the server copy. Use **My manuscripts → Save a copy** to keep the conflicting work.
- Use **Export** for Markdown or **Menu → Save as** for a `.2i` copy with document state, locks, references, and conversations.

## Connect your partner

Writing and saving work without a language model. Partner replies need your own running model service or configured cloud credential. The default is Ollama with model name `ministral-pubcast:3b`; change it to a model actually available on your computer. This package does not install model weights.

The gear’s connection test checks configuration/service availability. Sending a message confirms whether generation works. If the model is unavailable, the room reports that; it does not fabricate a partner reply.

Your personal Alex and System Alex have different roles. The selected personal partner receives this manuscript conversation; System Alex and Jeremy remain the shared coordination services. The separate personal Alex archive uploaded in chat has **not** been silently imported into this candidate.

## Marking your picture

Draw on a copy, label the action for each button, and keep its original 1344 × 896 canvas without cropping. You can also use **Menu → Show clickable areas** to inspect the placement on your computer. The unmarked original is `2i/2i-assets/writers-room-art.webp`. Button rectangles are stored separately in `2i/2i-assets/hotspots.json` as `[left, top, width, height]` in original-image pixels. Artwork and controls scale together.

## What was checked

The desktop final pass passed **18 focused API/startup tests**. With the phone edition included, the combined editor suite now passes **16 component/state check groups** (the previous desktop-only revision passed 13). All **26 pictured controls** were clicked in the component check, and their positions were checked against the original image. Tests also cover a delayed save during document switching and separate recovery of multiple offline manuscripts. The earlier broader 74-test gate remains in the audit evidence. A fresh full-host launch over real HTTP and a stop/restart preserved the account, authentication token, and manuscript.

**This is a candidate, not approval to promote all of Reach to the canonical base.** Actual browser rendering was blocked in the review environment, Windows/macOS launchers were not executed here, and no live language model was connected. The later camera/handoff changes mentioned in the September 13 handoff were not included in the supplied source snapshot. See `WRITERS_ROOM_HANDOFF.md` for the detailed evidence and boundaries.
