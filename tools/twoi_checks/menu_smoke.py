"""Click every command in every 2i menu, in a real browser on the real host, and report what each one did.

Why: the menus dispatch to about a hundred commands. Unit tests cover their logic; this finds the command that
throws, the dialog that does not fit a phone screen, and the command that is offered but does nothing visible.

What it does for each enabled command: chooses it from its drop-down exactly as a person would, waits, then
records any script error, any message the command put in the conversation (that is how a command reports a
failure), and any dialog it opened with whether that dialog fits inside the window. Dialogs are then closed.
Browser prompts (confirm, prompt, alert) are dismissed, so nothing is deleted or discarded. Commands that leave the
page or need the operating system (see SKIP) are listed as skipped, not counted as working.

Run:  python tools/twoi_checks/menu_smoke.py            (on the real host; laptop and phone widths, prints a table)
      python tools/twoi_checks/menu_smoke.py --disk     (2i opened straight from the file, no host running)
      python tools/twoi_checks/menu_smoke.py --json out.json
Needs the project's requirements plus Playwright with Chromium. Exit code 1 if any command raised a script error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from host import PAGE_ON_DISK, open_writers_room, running_host  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

# Left out on purpose, with the reason. Everything else is exercised.
SKIP = [
    (re.compile(r"^Print\b", re.I), "opens the system print dialog"),
    (re.compile(r"^Open\b", re.I), "opens the system file chooser"),
    (re.compile(r"\bimport\b", re.I), "opens the system file chooser"),
    (re.compile(r"return to|leave|stand up|back to (the )?studio", re.I), "navigates away from 2i"),
]

OPEN_STATE = """() => {
  const fits = (el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.left >= -1 && r.top >= -1 && r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1; };
  const dialogs = Array.from(document.querySelectorAll('dialog[open]')).map(d => ({kind: 'dialog', id: d.id || d.getAttribute('aria-label') || '(unnamed)', fits: fits(d)}));
  const modals = Array.from(document.querySelectorAll('.modal-backdrop.open')).map(m => ({kind: 'modal', id: m.id || '(unnamed)', fits: fits(m.querySelector('.modal') || m)}));
  const menu = document.getElementById('hamburgerMenu');
  return {dialogs: dialogs.concat(modals), hamburger: !!menu && menu.classList.contains('open'), notices: document.querySelectorAll('#chatLog .chat-msg').length, url: location.pathname};
}"""

# What a command can change without opening anything. Compared before and after, so a command that works quietly
# (a zoom step, a lock, a view switch, a save) is told apart from one that did nothing at all.
FINGERPRINT = """() => ({
  view: document.body.dataset.twoiDesk || '', mode: coWriting ? 'collab' : 'write',
  zoom: getComputedStyle(document.documentElement).getPropertyValue('--zoom-manuscript').trim(),
  locks: lockedLines.size, paragraphs: committed.length, chapters: chapters.length, title: documentTitle,
  sidebar: document.getElementById('mainArea').className + '|' + (document.body.dataset.twoiDrawer || ''),
  saved: document.getElementById('saveIndicator').textContent,
  notes: (document.getElementById('pnLayer') || {childElementCount: 0}).childElementCount,
  document: typeof documentId === 'undefined' ? '' : documentId,
})"""

RESET = """() => {
  if (coWriting) { coWriting = false; updateModeUI(); }
  lockedLines = new Set();
  if (committed.join('\\n') !== 'Chapter one opens here.\\nA second paragraph follows it.\\nAnd a third.') {
    loadDocState({committed: ['Chapter one opens here.', 'A second paragraph follows it.', 'And a third.'], coWriting: false}); markDirty();
  }
  render();
}"""

CLOSE_ALL = """() => {
  document.querySelectorAll('dialog[open]').forEach(d => d.close());
  document.querySelectorAll('.modal-backdrop.open').forEach(m => m.classList.remove('open'));
  const menu = document.getElementById('hamburgerMenu'); if (menu) menu.classList.remove('open');
  if (typeof closeRefViewer === 'function') closeRefViewer();
}"""


def run(browser, login, width, height, touch):
    context = browser.new_context(viewport={"width": width, "height": height}, has_touch=touch, is_mobile=touch, accept_downloads=True)
    if login:
        page = open_writers_room(context, login)
    else:  # opened on its own, straight from the file, with no host running anywhere
        page = context.new_page()
        page.goto(PAGE_ON_DISK)
        page.wait_for_function("!!document.getElementById('twoiMenuBar') && typeof initializing !== 'undefined' && !initializing", timeout=30000)
        page.wait_for_timeout(400)
    errors: list[str] = []
    prompts: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)[:200]))
    page.on("dialog", lambda d: (prompts.append(f"{d.type}: {d.message[:80]}"), d.dismiss()))
    downloads: list[str] = []
    page.on("download", lambda d: downloads.append(d.suggested_filename))
    # a little real manuscript, so commands that need text or a selection have something to work on
    page.evaluate("""() => { if (coWriting) { coWriting = false; updateModeUI(); }
        loadDocState({committed: ['Chapter one opens here.', 'A second paragraph follows it.', 'And a third.'], coWriting: false}); markDirty(); render(); }""")
    page.wait_for_timeout(300)
    menus = page.evaluate("""() => Array.from(document.querySelectorAll('#twoiMenuBar select')).map(s => s.getAttribute('aria-label'))""")
    rows = []
    for menu in menus:
        selector = f'#twoiMenuBar select[aria-label="{menu}"]'
        page.evaluate(f"document.querySelector('{selector}').dispatchEvent(new Event('focus'))")
        options = page.evaluate(f"""Array.from(document.querySelector('{selector}').options).slice(1).map((o, i) => ({{index: i + 1, name: o.textContent, disabled: o.disabled}}))""")
        for option in options:
            row = {"menu": menu, "command": option["name"], "result": "", "detail": ""}
            rows.append(row)
            skip = next((why for pattern, why in SKIP if pattern.search(option["name"])), None)
            if skip:
                row["result"], row["detail"] = "skipped", skip
                continue
            # availability is re-read just before each use, as the menu itself does when it is opened
            page.evaluate(f"document.querySelector('{selector}').dispatchEvent(new Event('focus'))")
            if page.evaluate(f"document.querySelector('{selector}').options[{option['index']}].disabled"):
                row["result"] = "unavailable"
                continue
            page.evaluate(RESET)  # every command starts from the same three-paragraph manuscript in Write mode
            before = page.evaluate(OPEN_STATE)
            print_before = page.evaluate(FINGERPRINT)
            errors.clear()
            prompts.clear()
            downloads.clear()
            try:
                page.select_option(selector, index=option["index"], timeout=3000)
            except Exception as exc:  # the control itself could not be used
                row["result"], row["detail"] = "could not choose", str(exc)[:120]
                continue
            page.wait_for_timeout(350)
            after = page.evaluate(OPEN_STATE)
            if after == before and not errors and not prompts and not downloads and page.evaluate(FINGERPRINT) == print_before:
                page.wait_for_timeout(2200)  # some commands load their screen on demand (studio notes) or wait on the host
                after = page.evaluate(OPEN_STATE)
            details = []
            if errors:
                row["result"] = "SCRIPT ERROR"
                details.append("; ".join(errors))
            new_notices = after["notices"] - before["notices"]
            if new_notices > 0:
                text = page.evaluate(f"Array.from(document.querySelectorAll('#chatLog .chat-msg')).slice(-{new_notices}).map(n => n.textContent.replace(/^PubPartner/, '').trim().slice(0, 110))")
                details.append("said: " + " | ".join(text))
            for d in after["dialogs"]:
                details.append(f"opened {d['kind']} {d['id']}" + ("" if d["fits"] else " — DOES NOT FIT THE WINDOW"))
            if prompts:
                details.append("asked: " + " | ".join(prompts))
            if after["url"] != before["url"]:
                details.append("LEFT THE PAGE: " + after["url"])
            if downloads:
                details.append("downloaded " + ", ".join(downloads))
            print_after = page.evaluate(FINGERPRINT)
            changed = [k for k in print_before if print_before[k] != print_after[k]]
            if changed:
                details.append("changed " + ", ".join(f"{k}: {print_before[k]!r} → {print_after[k]!r}"[:70] for k in changed))
            if not row["result"]:
                misfit = any(not d["fits"] for d in after["dialogs"])
                row["result"] = "DOES NOT FIT" if misfit else ("ok" if details else "ok (no visible sign)")
            row["detail"] = "  ".join(details)
            page.evaluate(CLOSE_ALL)
            page.wait_for_timeout(120)
    context.close()
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", type=Path, help="also write the full result to this file")
    parser.add_argument("--only", choices=["laptop", "phone"], help="run one width only")
    parser.add_argument("--disk", action="store_true", help="open 2i straight from the file with no host running, instead of on the host")
    args = parser.parse_args()
    sizes = {"laptop": (1280, 800, False), "phone": (390, 844, True)}
    if args.only:
        sizes = {args.only: sizes[args.only]}
    results = {}
    if args.disk:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            for name, (w, h, touch) in sizes.items():
                results[name + ", from disk"] = run(browser, None, w, h, touch)
            browser.close()
    else:
        with running_host() as login, sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            for name, (w, h, touch) in sizes.items():
                results[name] = run(browser, login, w, h, touch)
            browser.close()
    failed = 0
    for name, rows in results.items():
        counts: dict[str, int] = {}
        for r in rows:
            counts[r["result"]] = counts.get(r["result"], 0) + 1
        print(f"\n== {name}: {len(rows)} commands — " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
        for r in rows:
            if r["result"] != "ok":
                print(f"  [{r['result']}] {r['menu']} › {r['command']}  {r['detail']}")
        failed += counts.get("SCRIPT ERROR", 0)
    if args.json:
        args.json.write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
