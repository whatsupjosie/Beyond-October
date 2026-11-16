"""Measure the 2i layout in a real browser, on the real host and opened from disk, at laptop and phone sizes.

For each size it records where the page, the side panels, the drawer tabs, the menus and Save actually are, whether
anything overlaps or is cut off, and any script error; at phone sizes it also opens and closes each drawer and
checks that typed text and a half-typed message survive. It saves one screenshot per state. Read-only: nothing in
the repository or under ``data/`` is changed (see host.py).

Run:  python tools/twoi_checks/layout_probe.py OUTPUT_FOLDER        (prints a JSON report, writes PNG files there)
Needs the project's requirements plus Playwright with Chromium.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from host import PAGE_ON_DISK, running_host  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "twoi_layout_probe").resolve()

MEASURE = """
() => {
  const box = (el) => { if (!el) return null; const r = el.getBoundingClientRect(); return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)}; };
  const $ = (id) => document.getElementById(id);
  const vis = (el) => !!el && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none' && el.getBoundingClientRect().width > 0;
  const inView = (b) => !!b && b.w > 0 && b.x >= -1 && b.y >= -1 && b.x + b.w <= innerWidth + 1 && b.y + b.h <= innerHeight + 1;
  const overlap = (a, b) => !!a && !!b && a.w > 0 && b.w > 0 && a.x < b.x + b.w - 1 && b.x < a.x + a.w - 1 && a.y < b.y + b.h - 1 && b.y < a.y + a.h - 1;
  const menu = $('twoiMenuBar');
  const items = menu ? Array.from(menu.children) : [];
  const clipped = items.filter(e => { const r = e.getBoundingClientRect(), m = menu.getBoundingClientRect(); return r.right > m.right + 1 || r.left < m.left - 1 || r.right > innerWidth + 1; }).length;
  const budget = $('narrativeBudget'), ref = $('refSection'), mc = $('mcSection');
  const writing = vis($('soloTextarea')) ? $('soloTextarea') : $('manuscriptLines');
  const topRight = Array.from(document.querySelectorAll('.top-right > *')).filter(vis).map(box);
  let topOverlap = false;
  for (let i = 0; i < topRight.length; i++) for (let j = i + 1; j < topRight.length; j++) if (overlap(topRight[i], topRight[j])) topOverlap = true;
  const shelf = $('shelfBtn');
  return {
    viewport: {w: innerWidth, h: innerHeight},
    docScroll: {w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight},
    desk: document.body.dataset.twoiDesk || null,
    drawer: document.body.dataset.twoiDrawer || null,
    formatCore: typeof TwoiFormatCore,
    menu: menu ? {box: box(menu), scrollWidth: menu.scrollWidth, clientWidth: menu.clientWidth, items: items.length, clipped, classes: menu.className} : null,
    appShell: box(document.querySelector('.app-shell')),
    statusBar: box(document.querySelector('.status-bar')), shellBottom: Math.round(document.querySelector('.app-shell').getBoundingClientRect().bottom), frameBottom: Math.round($('notebookFrame').getBoundingClientRect().bottom), topBar: box(document.querySelector('.top-bar')), topDoc: {title: box($('docTitleDisplay')), words: box($('wordCount')), state: box($('saveIndicator'))},
    saveBtn: box($('saveBtn')), saveInView: inView(box($('saveBtn'))),
    notebookFrame: box($('notebookFrame')), writing: box(writing),
    sidebar: {box: box($('sidebar')), visible: vis($('sidebar')), inView: inView(box($('sidebar'))), scrollH: $('sidebar').scrollHeight, clientH: $('sidebar').clientHeight},
    chat: {box: box($('chatSection')), visible: vis($('chatSection')), inView: inView(box($('chatSection'))), parent: $('chatSection').parentElement.id},
    tabs: {tools: {box: box($('twoiDrawerTabTools')), visible: vis($('twoiDrawerTabTools'))}, partner: {box: box($('twoiDrawerTabPartner')), visible: vis($('twoiDrawerTabPartner'))}},
    tabOverWriting: overlap(box($('twoiDrawerTabTools')), box(writing)) || overlap(box($('twoiDrawerTabPartner')), box(writing)),
    budget: budget ? {box: box(budget), font: getComputedStyle(budget).fontFamily.slice(0, 40), size: getComputedStyle(budget).fontSize} : null,
    mcSection: box(mc), refSection: box(ref), refList: box($('refListContainer')), addRef: box($('addRefBtn')),
    mcOverRef: overlap(box(mc), box(ref)), budgetOverRef: overlap(box(budget), box(ref)),
    addRefInsideSidebar: (() => { const a = box($('addRefBtn')), s = box($('sidebar')); return !!a && !!s && a.y + a.h <= s.y + s.h + 1 + ($('sidebar').scrollHeight - $('sidebar').clientHeight); })(),
    shelfBtn: box(shelf), shelfTextFits: shelf ? shelf.scrollWidth <= shelf.clientWidth + 1 && shelf.scrollHeight <= shelf.clientHeight + 1 : null,
    topRightOverlap: topOverlap,
  };
}
"""


def open_page(browser, width, height, *, login=None, url=None, touch=False):
    context = browser.new_context(viewport={"width": width, "height": height}, has_touch=touch, is_mobile=touch,
                                  device_scale_factor=2 if touch else 1)
    page = context.new_page()
    errors, failed = [], []
    page.on("pageerror", lambda e: errors.append(str(e)[:300]))
    page.on("response", lambda r: failed.append(f"{r.status} {r.url[-80:]}") if r.status >= 400 and "/documents/" not in r.url else None)
    if login:
        base, user, password = login
        page.goto(base + "/login?next=%2Fwriters-room")
        page.fill("#loginUser", user)
        page.fill("#loginPass", password)
        page.keyboard.press("Enter")
        page.wait_for_url("**/writers-room**", timeout=20000)
    else:
        page.goto(url)
    page.wait_for_timeout(2500)
    return context, page, errors, failed


def snap(page, name):
    page.wait_for_timeout(450)
    page.screenshot(path=str(OUT / name))
    return page.evaluate(MEASURE)


def scenario(browser, label, width, height, *, login=None, url=None, touch=False, drawers=False):
    context, page, errors, failed = open_page(browser, width, height, login=login, url=url, touch=touch)
    out = {"page": snap(page, f"{label}.png")}
    if drawers:
        tap = (lambda sel: page.tap(sel)) if touch else (lambda sel: page.click(sel))
        # type something first: it must survive every drawer movement
        page.evaluate("() => { if (typeof coWriting !== 'undefined' && coWriting) { coWriting = false; updateModeUI(); } }")
        tap("#soloTextarea")
        page.keyboard.type("Line typed before any drawer opened.")
        before = page.evaluate("soloTextarea.value")
        tap("#twoiDrawerTabTools")
        out["tools_open"] = snap(page, f"{label}_tools.png")
        out["tools_open"]["focusId"] = page.evaluate("document.activeElement && (document.activeElement.id || document.activeElement.className)")
        out["tools_open"]["pageInert"] = page.evaluate("document.getElementById('notebookFrame').inert")
        tap("#twoiDrawerTabTools")
        out["tools_closed"] = page.evaluate("({drawer: document.body.dataset.twoiDrawer || null, focusId: document.activeElement.id, inert: document.getElementById('notebookFrame').inert})")
        if page.evaluate("getComputedStyle(document.getElementById('twoiDrawerTabPartner')).display !== 'none'"):
            tap("#twoiDrawerTabPartner")
            page.fill("#chatInput", "half-typed message")
            out["partner_open"] = snap(page, f"{label}_chat.png")
            page.keyboard.press("Escape")
            page.wait_for_timeout(350)
            out["partner_closed_by_escape"] = page.evaluate("document.body.dataset.twoiDrawer || null")
            tap("#twoiDrawerTabPartner")
            page.wait_for_timeout(350)
            out["chat_text_kept"] = page.evaluate("document.getElementById('chatInput').value")
            # backdrop closes
            page.mouse.click(8, 4 + height // 2) if not touch else page.touchscreen.tap(8, height // 2)
            page.wait_for_timeout(350)
            out["partner_closed_by_backdrop"] = page.evaluate("document.body.dataset.twoiDrawer || null")
        # the menu button opens the same left drawer
        tap("#sidebarToggle")
        page.wait_for_timeout(350)
        out["menu_button_opens"] = page.evaluate("document.body.dataset.twoiDrawer || null")
        page.keyboard.press("Escape")
        page.wait_for_timeout(350)
        out["text_kept"] = page.evaluate("soloTextarea.value") == before
        # widen past the breakpoint with a drawer open: panels must return to their places
        tap("#twoiDrawerTabTools")
        page.set_viewport_size({"width": 1280, "height": 800})
        page.wait_for_timeout(500)
        wide = page.evaluate(MEASURE)
        out["after_widening"] = {"drawer": wide["drawer"], "sidebarVisible": wide["sidebar"]["visible"], "chatVisible": wide["chat"]["visible"],
                                 "tabsVisible": wide["tabs"]["tools"]["visible"], "inert": page.evaluate("document.getElementById('notebookFrame').inert"),
                                 "text_kept": page.evaluate("soloTextarea.value") == before}
    out["pageErrors"] = errors
    out["failedRequests"] = failed[:8]
    context.close()
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = {}
    with running_host() as login, sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        result["hosted_1280x800"] = scenario(browser, "hosted_1280", 1280, 800, login=login)
        result["hosted_1000x700"] = scenario(browser, "hosted_1000", 1000, 700, login=login)
        result["hosted_1280x600"] = scenario(browser, "hosted_1280x600", 1280, 600, login=login)
        result["hosted_390x844"] = scenario(browser, "hosted_390", 390, 844, login=login, touch=True, drawers=True)
        result["hosted_320x568"] = scenario(browser, "hosted_320", 320, 568, login=login, touch=True, drawers=True)
        result["hosted_768x1024"] = scenario(browser, "hosted_768", 768, 1024, login=login, touch=True, drawers=True)
        result["hosted_844x390"] = scenario(browser, "hosted_844x390", 844, 390, login=login, touch=True, drawers=True)
        result["disk_1280x800"] = scenario(browser, "disk_1280", 1280, 800, url=PAGE_ON_DISK)
        result["disk_390x844"] = scenario(browser, "disk_390", 390, 844, url=PAGE_ON_DISK, touch=True, drawers=True)
        browser.close()
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
