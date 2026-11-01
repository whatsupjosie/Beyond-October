# Reach Writer’s Room — phone edition

Built September 13, 2026. Included in `Reach_Writers_Room_001.zip` alongside the reviewed desktop view.

## New controls

Use **☰** for the general menu and **⚙** for Settings. The top-right **—** shrinks the room to its header and compact reader; **×** closes the view and shows Reopen. Your current editor state is retained. Closing pauses/stops reading and waits for preservation.

The visible Audio panel has Read from start, Play/Pause/Resume, Stop, previous/next paragraph, and back/forward ten-word buttons. Expand its options for voice, reading speed, volume, source and reading from the cursor. Settings also changes manuscript text size. Read-aloud uses the phone/browser’s speech service; the live PubPartner voice remains unconnected in the local edition. If this chat/browser blocks speech, the panel explains the failure.

If you are using only a phone, the separate `Reach_Phone_Standalone.html` or the inline desk in the chat starts without a computer. It saves locally where storage is available and exports `.2i` copies for later use in Reach. The server-backed layout in the full ZIP still requires a running, reachable Reach host.

## Try the layout

1. Extract the updated build into its own folder and start Reach using `OPEN_REACH_WINDOWS.bat` or `bash open_reach.sh`.
2. Open **Menu → Phone view**. It works in a desktop window too, so you can inspect it before connecting a phone.
3. Use **Write**, **Partner**, and **Archive** to move around the room. **Save** and **My manuscripts** remain at the bottom.
4. **Whole desk picture** returns to your original picture with its mapped buttons. Switching views preserves the current editor, document, drafts, selection and conversation state.

The explicit phone entry is `http://127.0.0.1:8000/writers-room?view=phone` on the computer running Reach. Change the port if your installation uses another one. The explicit desktop entry ends in `?view=desktop`. A first visit at 600 CSS pixels wide or less selects the phone view automatically; resizing does not unexpectedly override your chosen view.

## What changes on a phone

The original uploaded image remains byte-identical. Its notebook area supplies the rings, parchment and worn edges of the writing panel, and its brass framing supplies the header. The complete landscape picture is available through Whole desk picture. The phone edition rearranges its existing controls into three panels, so they are not tiny scaled-down desktop hotspots.

- **Write:** readable 18-pixel manuscript text, scene outline, creation and navigation, writing modes, locks, draft commit and word goal.
- **Partner:** the selected personal partner, conversation, Send, suggestion insertion/dismissal and scene ideas.
- **Archive:** Characters, Worldbuilding, Notes, searchable/filterable references, adding and viewing references.
- **Always available:** settings, menu, Save, My manuscripts and Export. Buttons have minimum 48-by-48 CSS-pixel targets. The center pane scrolls; the viewport-height handler accommodates a smaller visible viewport when the keyboard opens.

Both layouts move the same DOM controls instead of cloning editors. They use the same authenticated manuscript APIs and existing integrated PubPartner runtime. This layout does not create another System Alex/Jeremy pair, merge partner identities, or import the private Alex archive.

## Using an actual cell phone

Reach still runs on the computer. The current launcher binds `127.0.0.1`, so another device cannot connect directly. A phone needs a separately configured, authenticated address that reaches that host. This update does not publish the build, open network ports, or configure that connection. The loopback URL on a phone refers to the phone itself.

After a reachable address is configured, open its `/writers-room?view=phone` page, sign in to the same account, and select **My manuscripts**. Server-saved manuscripts are available to that account on both devices. Browser recovery copies remain in their own browser until saved to Reach. Concurrent edits still trigger the existing revision-conflict protection.

The phone view is a web interface, not a native iPhone/Android app. A language model still needs to be configured for real partner replies; writing and saving do not require model generation.

## What was verified

- Combined desktop and phone component/state suite: **16 PASS groups**.
- The phone layout contains all 26 original mapped controls once, with their original handlers, visible captions and declared 48-pixel minimum heights. The manuscript’s computed font size is 18 pixels.
- Writing/save, synthetic partner reply → draft → commit, reference search/view, settings, exports and manuscript shelf were exercised.
- Repeated desktop/phone switching preserved the exact editor element, document identifier, unsaved document state, and original desktop coordinates.
- Tab keyboard navigation and state/height handling were checked at 320×568, 360×800, 390×844, 430×932, 844×390 and a shortened 390×390 viewport. These are DOM/state assertions, not screenshots or measured browser layouts.
- The complete bootstrap served the phone entry and exact CSS/JS assets over real HTTP; account setup, save/read and process restart also passed.
- The earlier focused desktop API/startup gate passed 18 tests; the mobile change did not alter backend or launcher source.

**Still unverified:** real phone/browser rendering, actual touch hit testing, font wrapping, on-screen keyboard behavior, a phone-to-computer connection, native Windows/macOS startup and live model generation. Browser rendering was blocked by this environment’s browser security policy; it was not worked around. This is a candidate for local visual review, and the whole Reach build is not approved as the canonical base.

Evidence: `writer_room_audit/phone-editor.log`, `phone-http.json`, and the existing final-pass evidence. Reproduce with `npm --prefix writer_room_audit ci`, `npm --prefix writer_room_audit test`, and `python tests/probe_reach_http.py --launcher start_reach.py` in the configured test environment. The Python probe requires HTTPX. Read `WRITERS_ROOM_HANDOFF.md` for the earlier audit, limitations and preservation record.
