# 2i live preview in a browser

This branch starts from the **2i + Claude functional integration** commit
`5d21ec1ac772e5026aa99d829e7918813ee15844`. No existing branch is merged or changed.

## Open

1. Use GitHub **Code > Codespaces > Create codespace** on this branch.
   On GitHub Free, Codespaces has a monthly included quota.
2. Codespaces installs Python and Node dependencies on first creation and
   launches Reach automatically. If the preview is slow to appear, inspect
   `.preview-runtime/2i.log` in the Codespace.
3. Open the **PORTS** tab and select **Open in Browser** for port **8000**.
   Append `/writers-room` to the forwarded URL.
4. Set up the local Reach login if prompted. The port is configured **private**,
   not open to the public.

The editor and its optional Node sidecar run together under `run_reach.py`.
This is a **development preview**, not a production launch, and it has **not**
been browser-acceptance-tested in Codespaces.

Your files in the Codespace are **not** the files on your PC. Export any
manuscript to your own device before deleting your Codespace. Do not rely on
the current beta's Save Now alone as your only backup.

## If startup fails

Open a terminal in Codespaces and run:

```sh
bash .devcontainer/start-2i-preview.sh
cat .preview-runtime/2i.log
```

The code that matters remains on `codex/2i-claude-functional-integration-2026-11-17`
and its ancestor branches. This preview branch only adds launch infrastructure.
