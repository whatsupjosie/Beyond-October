# PubCast/Foresight continuous-run checkpoint

## Verified fixes
- Added four missing packaged first-run bot defaults to `data/bots/`: `pete.json`, `jeremy.json`, `repeat.json`, `sir_purfluous.json`. These are copied from the packaged existing `reach_userdata/bots` and allow `_seed_packaged_bot_configs` to initialize a fresh user-data folder. Existing user files are never overwritten by that function.
- Added `.github/workflows/foresight-workbench.yml` to run selected integration and regression tests on push, pull request, and manual dispatch. Workflow is packaged but **has not been executed on GitHub**.

## Local evidence
- Initial broader regression: **1 failed, 69 passed**, revealing the missing first-run bot defaults.
- After fix: **70 passed** in 23.61 seconds.
- `node --check` passed for four Counter JS modules.

## Unverified acceptance criteria
- GUI interactions in real Chromium with full running Reach.
- Windows launcher on target machine.
- Live 2i save/reopen through a tray.
- Live provider-backed Pub Partner turn through a tray.
- Avatar/body/environment interaction.

## Next engineering actions
- Run the GitHub Actions workflow in the actual repo, resolve any environment-specific failures.
- Run real browser UI checks with Reach and credentials on the target machine.
- Test 2i save/reopen, Pub Partner send/receive, and Counter workspace restore as end-to-end scenarios.
- Do not call the workbench certified until those interactions pass.
