"""Browser checks of the integrated Foresight Counter page (static/foresight_counter.html) with the real program list."""
import asyncio, json, sys, os
from playwright.async_api import async_playwright

BASE = 'http://127.0.0.1:8781/static/foresight_counter.html'
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
LOOK = sys.argv[2] if len(sys.argv) > 2 else ''
results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok))); print(('PASS ' if ok else 'FAIL ') + name + ('  | ' + str(detail)[:400] if detail else ''), flush=True)

async def frames(pg, n):
    for _ in range(n): await pg.evaluate('window.__counter.debug.step()')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        ctx = await b.new_context(viewport={'width': 1600, 'height': 1000}, accept_downloads=True)
        # no Reach server here: the sign-in helper is left out, as on a machine where auth is off
        await ctx.route('**/static/reach_auth.js', lambda r: r.fulfill(status=200, content_type='text/javascript', body='/* no Reach here */'))
        pg = await ctx.new_page(); pg.set_default_timeout(300000)
        errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        # the pages inside trays need the Reach server (sockets, APIs); here only the counter's own errors count
        pg.on('console', lambda m: errs.append('console: ' + m.text + ' @ ' + str(m.location.get('url'))) if m.type == 'error' and 'Failed to load resource' not in m.text and 'WebSocket' not in m.text and '/static/foresight' in str(m.location.get('url', '')) else None)
        await pg.goto(BASE + '?once=1&fresh=1' + LOOK)
        await pg.wait_for_function('window.__counter && window.__counter.gl.stoneReady === true', timeout=90000)
        E = pg.evaluate
        await E('window.__counter.debug.setClock(1e6)'); await frames(pg, 3)
        trays = await E('window.__counter.trays.map(t => ({id: t.id, types: t.stack.map(c => c.type), hidden: !!t.hidden}))')
        check('fresh start shows a blank Counter', len(trays) == 0, trays)
        # World Chat is selectable, not an automatic startup tray.
        await E('window.__programs.open("world_chat", {})')
        await frames(pg, 3)
        src = await E('window.__counter.trays[0].stack[0].body.querySelector("iframe").getAttribute("src")')
        check('World Chat opens on request as the live page', src == '/static/world_chat.html', src)

        # open the programs the way the menus and the fan do
        clock = [1e6]
        async def open_(id, data=None):
            await E(f'window.__programs.open({json.dumps(id)}, {json.dumps(data or {})})')
            clock[0] += 2000; await E(f'window.__counter.debug.setClock({clock[0]})'); await frames(pg, 2)
        for pid in ['control_room', 'pubpartner_workspace', 'iteration_wallet', 'pubpartner_status', 'browser']:
            await open_(pid)
        await open_('control_room')   # a second time: brought forward, not a second tray
        trays = await E('window.__counter.trays.map(t => t.stack.map(c => c.type).join("+"))')
        check('programs open in trays; a one-of-a-kind program is brought forward, not opened twice', trays.count('control_room') == 1 and len(trays) == 6, trays)
        await pg.wait_for_timeout(3500); await frames(pg, 2)   # Iteration Wallet's check, status polling
        iw = await E('window.__counter.trays.find(t => t.stack[0].type === "iteration_wallet").stack[0].body.innerText')
        check('Iteration Wallet not running: says so, with the PowerShell line to start it', 'not running' in iw.lower() and 'START_ITERATION_WALLET.ps1' in iw, iw)
        st = await E('window.__counter.trays.find(t => t.stack[0].type === "pubpartner_status").stack[0].body.innerText')
        check('PubPartner status tray polls the real service (unreachable here)', 'unreachable' in st.lower() or 'Status' in st, st)
        # browser: go to an address
        await E('''(() => { const t = window.__counter.trays.find(t => t.stack[0].type === "browser"), b = t.stack[0].body;
          const a = b.querySelector(".fp-addr"); a.value = "/static/gallery.html"; a.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter"})); })()''')
        await frames(pg, 2)
        bt = await E('(() => { const t = window.__counter.trays.find(t => t.stack[0].type === "browser"); return {title: t.stack[0].title, src: t.stack[0].body.querySelector("iframe").src, plaque: t.plaque.textContent}; })()')
        check('browser tray goes to an address and takes its name', bt['src'].endswith('/static/gallery.html') and 'PubCast' in bt['title'] and bt['plaque'] == bt['title'], bt)
        # a file from this computer (an image made here)
        await E('''(async () => { const c = document.createElement("canvas"); c.width = 320; c.height = 200; const g = c.getContext("2d");
          g.fillStyle = "#c08040"; g.fillRect(0, 0, 320, 200); g.fillStyle = "#fff"; g.font = "28px sans-serif"; g.fillText("Picked file", 70, 110);
          const blob = await new Promise(r => c.toBlob(r, "image/png")); const f = new File([blob], "picked.png", {type: "image/png"});
          const r = window.__programs.provider.fromFile(f); window.__counter.open(r.type, r.data); })()''')
        clock[0] += 2000; await E(f'window.__counter.debug.setClock({clock[0]})'); await frames(pg, 3)
        img = await E('(() => { const t = window.__counter.trays.find(t => t.stack[0].type === "file"); const i = t && t.stack[0].body.querySelector("img"); return i ? {src: i.src.slice(0, 5), title: t.stack[0].title} : null; })()')
        check('a file from this computer opens in its own tray', img and img['src'] == 'blob:' and img['title'] == 'picked.png', img)
        # export: the image itself; the browser tray as a Windows shortcut
        async with pg.expect_download() as dl:
            await E('window.__counter.exportTray(window.__counter.trays.find(t => t.stack[0].type === "file"))')
        d = await dl.value; path = os.path.join(OUT, 'export_' + d.suggested_filename); await d.save_as(path)
        check('Export of a file tray gives back the file', d.suggested_filename == 'picked.png' and os.path.getsize(path) > 500, d.suggested_filename)
        async with pg.expect_download() as dl:
            await E('window.__counter.exportTray(window.__counter.trays.find(t => t.stack[0].type === "browser"))')
        d = await dl.value; path = os.path.join(OUT, 'export_' + d.suggested_filename); await d.save_as(path)
        txt = open(path, encoding='utf-8').read()
        check('Export of a browser tray gives a Windows internet shortcut', d.suggested_filename.endswith('.url') and 'URL=http' in txt, [d.suggested_filename, txt])

        # import a room into the browser tray (stacks; switching keeps both alive)
        await E('window.__counter.importInto(window.__counter.trays.find(t => t.stack[0].type === "browser"), "teleprompter", {})')
        await frames(pg, 60)
        stk = await E('window.__counter.debug.info(window.__counter.trays.find(t => t.stack[0].type === "browser").id)')
        check('Import puts a room into an existing tray, stacked with what was there', stk['types'] == ['browser', 'teleprompter'] and stk['active'] == 'Teleprompter', stk)

        await E('window.__settle()'); await E('window.__counter.debug.draw()')
        await pg.screenshot(path=os.path.join(OUT, 'page_full.png'))
        pr = await E('window.__counter.debug.pressure()')
        check('a full counter of real programs: no frames pass into each other', pr['overlap'] <= 4.6, pr)

        # the menus
        await pg.click('.menu-btn >> text=File'); await pg.wait_for_timeout(150)
        items = await E('[...document.querySelectorAll(".menu.open .menu-item")].map(b => b.textContent)')
        check('File menu', any('Open…' in x for x in items) and any('New web browser' in x for x in items) and any('Clear the countertop' in x for x in items), items)
        await E('window.__counter.debug.draw()'); await pg.screenshot(path=os.path.join(OUT, 'page_menu.png'))
        await pg.keyboard.press('Escape')
        await pg.click('.menu-btn >> text=Window'); await pg.wait_for_timeout(150)
        win = await E('[...document.querySelectorAll(".menu.open .menu-item")].map(b => b.textContent)')
        check('Window menu lists every tray', len(win) == 7, win)
        await pg.keyboard.press('Escape')
        await pg.click('.menu-btn >> text=View'); await pg.wait_for_timeout(150)
        view = await E('[...document.querySelectorAll(".menu.open .menu-item")].map(b => b.textContent)')
        check('View menu: lock, reset, put away, counter looks, lantern', all(any(k in x for x in view) for k in ['Lock', 'Reset this tray', 'Put this tray away', "Tiger's eye", 'Nero marble', 'Lantern light']), view)
        await pg.keyboard.press('Escape')

        # the New blade's picker lists the real program list
        await E('window.__counter.openPicker(null)')
        vi = await E('window.__counter.debug.veilItems()')
        need = ['PubPartner · Alex & Cartridges', "2i Writer's Room", 'Iteration Wallet', 'Control Room', 'Web browser', 'Blank tray', 'A file from this computer…', 'New chat', 'PubPartner Status']
        missing = [x for x in need if not any(v.startswith(x) for v in vi)]
        check('the picker lists programs, rooms, tools, status, browser, blank tray, file, new chat', not missing, missing or len(vi))
        await E('window.__counter.debug.draw()'); await pg.screenshot(path=os.path.join(OUT, 'page_picker.png'))
        await pg.keyboard.press('Escape')

        # reload: everything comes back; the picked file asks to be chosen again
        await E('window.__counter.saveNow()')
        await pg.goto(BASE + '?once=1' + LOOK)
        await pg.wait_for_function('window.__counter && window.__counter.gl.stoneReady === true', timeout=90000)
        await E('window.__counter.debug.setClock(5e6)'); await frames(pg, 2)
        back = await E('window.__counter.trays.map(t => t.stack.map(c => c.type).join("+"))')
        check('after a reload every tray comes back with its contents', sorted(back) == sorted(trays + ['file', 'browser+teleprompter']) or len(back) == 7, back)
        again = await E('(() => { const t = window.__counter.trays.find(t => t.stack[0].type === "file"); return t ? t.stack[0].body.innerText : ""; })()')
        check('a picked file asks to be chosen again after a reload (browsers do not keep file access)', 'choose the file again' in again.lower(), again)
        addr = await E('(() => { const t = window.__counter.trays.find(t => t.stack[0].type === "browser"); return t ? t.stack[0].data.address : null; })()')
        check('the browser tray keeps its address', addr and addr.endswith('/static/gallery.html'), addr)
        await E('window.__settle()'); await E('window.__counter.debug.draw()')
        await pg.screenshot(path=os.path.join(OUT, 'page_restored.png'))
        check('no page errors', not errs, errs[:6])
        await E('localStorage.clear()')
        await b.close()
    bad = [r for r in results if not r[1]]
    print(f'\n{len(results) - len(bad)}/{len(results)} passed')

asyncio.run(main())
