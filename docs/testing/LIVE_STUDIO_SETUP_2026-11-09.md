# Live studio setup and executed workflows

Source: Beyond-October, gpt/control-ui-wiring-2026-11-08 at e86d20b. Work branch: gpt/live-studio-setup-2026-11-09. No main merge or production deployment.

## RAN

Installed canonical requirements into the existing isolated Python 3.12 runner. Installed the pinned Playwright 1.56 Chromium 141.0.7390.37 using the installer's working official mirror after the primary CDN supplied an invalid archive. The real browser smoke test passed.

Ran these real authenticated host/browser tests together, using generated test users and disposable data:

- tests/test_production25d_browser.py::test_two_real_pages_share_cut_and_actual_remote_frames
- tests/test_production25d_browser.py::test_real_recording_reopens_after_reload_and_plays
- tests/test_studio25d_archive_browser.py::test_completed_take_reopens_from_server_after_browser_and_host_restart

Result: 3 passed, 0 failed, 0 skipped, 54.78 seconds. Starlette/AnyIO deprecation and pytest-asyncio configuration warnings remain.

The archive case captured an actual WebM, interrupted an upload after the server committed a chunk, restarted the server twice, resumed without retransmitting the committed chunk, matched SHA-256 and byte length, opened playback in a fresh browser context with no local sessions, and downloaded an archive whose media bytes matched. Actual observed file: 94,050 bytes, 1280 by 720 video. FFmpeg decoded audio at 48 kHz; dominant test tone 439.86 Hz with RMS 0.144. This is generated test audio, not microphone evidence. Local screenshot and recording artifacts remain internal.

## Running preview

Added a small isolated preview launcher and npm dev entry. It uses the existing host, seeds packaged bot configurations, enforces authentication, and reuses the existing persistent JWT secret helper. It accepts the preview runner's host/port arguments. It does not install packages at startup. First owner setup is left for the user inside the application.

The managed preview initially failed because its Python runtime had neither uvicorn nor pip. Its runtime was confirmed as Python 3.12.3 on x86_64. Prepared already-installed Python 3.12 dependencies in the checkout-local .preview-python directory; excluded that directory and all preview runtime directories through local Git exclusions. No runtime data or credentials are staged.

Executed managed preview successfully: http://terminal.local:4173/. The actual PubCast sign-in page loaded in the cloud browser. This is a cloud-browser preview address, not an Internet URL for independent Android Chrome. The owner can interact through the cloud browser panel on the phone. No public tunnel was established.

Explicit preparation for another compatible managed Python 3.12 environment: install requirements into .preview-python before invoking the preview runner. The managed preview launcher must be used with an accessible Python interpreter and those dependencies prepared. No new hosted Site was created and no permanent hosting was purchased.

## UNKNOWN / next

The user must complete first-owner setup in the preview UI. Their first interactive studio run in this cloud browser is not yet accepted. The automated workflow tests used local Chromium with software WebGL; cloud-browser graphics capability may differ. Physical Android Chrome, real camera/microphone, GPU performance, production-length capture, source-master completeness and finishing import remain unverified. These three selected workflow passes are not a whole-program or market-readiness claim.

The preview is temporary. Durable shooting needs a user-owned host with persistent storage; this preview should be used for disposable testing. The next engineering step is the full operator-led run of the studio plus the complete station/recording regression suite, followed by failure-specific fixes.

## Profile completion follow-up

The first owner account was successfully created by the user in the cloud browser. The remaining obstruction was the long optional profile form, not registration. The actual remote viewport was only 237 pixels tall. Scrolled the existing page to expose Save profile and Skip optional details without submitting, changing the profile, or refreshing away user input.

Moved the existing Save/Skip controls into a fixed bottom action group within the same form. Preserved their IDs, handlers, account privacy choices and all fields. Added bottom page clearance and safe-area padding so later content can scroll above the controls. No authentication or profile API behavior changed.

RAN: tests/test_human_profile_onboarding_browser.py — 5 passed, 0 failed/skipped in 14.91 seconds. Includes the original private/discoverable first-owner creation and skip flows, plus 390x844, 390x300 and 842x237 viewports. At both scroll extremes the two completion buttons remain inside the viewport, at least 44 pixels tall and clickable by hit testing; the last profile input can scroll clear of the action bar. Reduced viewport height models constrained screen space, not an actual Android keyboard test. git diff --check passed. The modern guidance npm package was unavailable in the offline cache; the fix uses ordinary fixed-position CSS with safe-area fallback.

The currently open user form is preserved without a forced refresh. The footer fix is applied when the profile page is loaded again.

## Touch navigation and user-chosen passwords

Owner requested finger scrolling/dragging and passwords such as `cat` or `A`, without a composition policy. Implemented both on the existing work branch.

- Setup, login, profile and television studio/Director pages opt into a small shared remote-viewer drag-scroll helper. Native touch and pen are left to the browser. For viewers that send mouse events, dragging a blank page area scrolls the nearest scroll container and then its ancestors. Interactive controls, labels, text selection on text elements, canvases and iframes are excluded; pointer cancellation, lost capture, button release and window blur clean up a grab. No global touchmove cancellation or forced touch-action:none is added.
- Removed password composition, predictable-word, username-match and length policy checks. Any nonempty string is accepted exactly, including one character, whitespace and Unicode. Setup confirmation, existing-account current-password verification, PBKDF2 hashing, auth enforcement and request rate limits remain in place. Updated the registration hint. No existing user's password was changed.

RAN: 23 passed, 0 failed, 0 skipped in 32.80 seconds across the touch-navigation browser tests, password-choice API tests, existing password-change test, auth-productization reference suite and first-owner/profile browser suite. Browser first-owner creation uses both `cat` and `A` with both profile visibility choices. API setup/login tests cover `cat`, `A`, username-equal, common words, whitespace, Unicode and a 300-character password; incorrect/empty login is rejected. Native Chromium touch events actually scroll the profile/studio, and mouse dragging their background scrolls independently. Text input stays editable. The prior short-viewport completion checks also pass.

Browser binaries did not survive this environment restart. An initial run correctly reported seven skipped browser cases (14 API tests passed); that is not acceptance evidence. Installed the pinned Chromium 141 headless shell from Playwright's official Microsoft mirror, passed a fresh interaction/screenshot smoke test, and reran all selected tests with zero skips. The first manual mirror override lacked the `/playwright` path component and failed; the corrected official URL succeeded. Deprecation/configuration warnings remain. Node syntax and git diff --check passed.

Restarted the authenticated managed preview successfully with these changes; existing runtime data and persistent signing secret were retained. No production publication, main merge or credential change occurred. The former cloud tab was no longer present when checked. Existing pages need reloading to load the new client script. Trusted touch events in desktop Chromium are emulation evidence, not physical Android testing.

## Camera sign-in artwork

Used the owner's existing `camera 2.jfif` image, visually inspected as the ornate camera with the Rearview Foresight plaque. Preserved the original bytes under static/brand/pubcast-camera.jpg, with source/hash recorded in static/brand/README.md. The asset is local, decorative and does not intercept gestures. The sign-in panel stays left on wider screens and centered on phones, with an opaque-enough background for reading. Improved low-contrast secondary text/link colors. Kept the page vertically scrollable and mobile input/button targets at least 44 pixels tall.

RAN: nine real Chromium onboarding/profile/touch tests passed, zero failures/skips, in 28.62 seconds. These include real setup with `cat` and `A`. Visually inspected the actual updated sign-in page in the running cloud browser: image loaded and camera plaque remained visible beside the panel. A subsequent color-only contrast adjustment was inspected in source; it does not alter behavior. No current account credentials were changed. No main merge or permanent publication.

## Recorded take and independent guest experiment

At the owner's request, confirmed the existing preview owner account/profile in the saved database without reading password hashes or changing the account. Optional onboarding was still incomplete, with no optional about fields saved. The temporary host was stopped after the environment restart; restarted it against the same saved runtime data. The cloud browser had no surviving tabs or authenticated session.

Recorded an actual short studio take in a separate authenticated test instance using the existing archive acceptance path. RAN: test_completed_take_reopens_from_server_after_browser_and_host_restart — 1 passed, zero failed/skipped in 27.60 seconds. Actual WebM: 79,903 bytes; VP9 1280x720 video, Opus 48 kHz audio. Inspected a decoded video frame and confirmed the news set and both rehearsal avatars are present. The audio is a generated test tone, not a microphone recording. Measured dominant tone 440.10 Hz, RMS 0.1503. SHA-256 `103eba9180451e58a61a1a851fecf2163262395f3a0da1bc8a60d9e08a3f0885`. The original bytes were preserved through server upload/resume, two host restarts, fresh-browser playback and source-bundle export. Delivered the WebM as PubCast_Studio_Test_Recording.webm.

The owner asked whether she needs to create another profile for guest experimentation. No: the test creates independent disposable identities on isolated home hosts. RAN: tests/test_admitted_guest_recording_browser.py — 1 passed, zero failed/skipped in 36.65 seconds. Two separately owned identities use signed visiting cards, owner approval and host-issued leases, contribute different generated audio tones, exercise mixing/reconnect/durable stems, and export original server media. Existing owner account/profile data were not changed by either test. These are software-media tests; physical microphones, Android input, real camera hardware and full production/master acceptance remain open.

The pinned browser again needed reinstallation after the environment restart. Installed Chromium 141 headless shell and FFmpeg through the previously verified official mirror and passed a fresh interaction/screenshot smoke test before the application runs. The Starlette/AnyIO and pytest-asyncio warnings remain. No application-code changes were required by these runs.
