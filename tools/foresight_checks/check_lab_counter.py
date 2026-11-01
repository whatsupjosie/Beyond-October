"""Browser checks of the Foresight Counter in the lab: every tray behaviour, driven through the module's own API."""
import asyncio, json, sys
from playwright.async_api import async_playwright

BASE = 'http://127.0.0.1:8781/foresight/lab/lab.html'
OUT = sys.argv[1] if len(sys.argv) > 1 else '.'
results = []

def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print(('PASS ' if ok else 'FAIL ') + name + ('  | ' + str(detail) if detail else ''), flush=True)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'], executable_path=os.environ.get('FORESIGHT_TEST_CHROMIUM') or None)
        ctx = await b.new_context(viewport={'width': 1600, 'height': 1000}, accept_downloads=True)
        pg = await ctx.new_page(); pg.set_default_timeout(300000)
        errs = []
        pg.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
        pg.on('console', lambda m: errs.append(m.type + ': ' + m.text + ' @ ' + str(m.location.get('url', ''))) if m.type == 'error' else None)
        pg.on('requestfailed', lambda r: errs.append('requestfailed: ' + r.url))
        pg.on('response', lambda r: errs.append('http ' + str(r.status) + ': ' + r.url) if r.status >= 400 else None)
        await pg.goto(BASE + '?once=1&fresh=1&lamp=0.3')
        await pg.wait_for_function('window.__counter && window.__counter.gl.stoneReady === true', timeout=90000)
        await pg.evaluate('window.__settle()')
        E = lambda js: pg.evaluate(js)
        D = 'window.__counter.debug'
        info = lambda i: E(f'{D}.info("{i}")')

        ids = await E('window.__counter.trays.map(t => t.id)')
        check('six trays laid out', len(ids) == 6, ids)
        pr = await E(f'{D}.pressure()')
        check('settled counter has no frames passing into each other', pr['overlap'] <= 4, pr)

        # walls: every frame point inside the counter
        inside = await E('''(() => { const c = window.__counter, W = innerWidth, H = innerHeight; let worst = 0;
            for(const t of c.trays){ if(t.hidden) continue; for(const p of t.q){ worst = Math.max(worst, -p[0], p[0]-W, 70-p[1], p[1]-H); } } return worst; })()''')
        check('every frame is on the counter', inside <= 0.5, inside)

        # stacked contents keep their state when switched
        f = await info('files')
        check('files tray holds three contents', len(f['stack']) == 3, f['stack'])
        await E('''(() => { const t = window.__counter.find('files'); const mixer = t.stack.find(c => c.type === 'audio.mixer');
            mixer.state.levels[2] = 0.11; mixer.state.mute[3] = true; })()''')
        await E('''(() => { const t = window.__counter.find('files'); window.__counter.openTrayMenu(t, 400, 400); })()''')
        items = await E(f'{D}.menuItems()')
        check('tray menu lists stacked contents and every action',
              all(any(x.endswith(n) for x in items) for n in ['Audio Mixer', 'Keyboard', 'Project Files']) and
              all(n in items for n in ['Reset tray', 'Lock tray', 'Import…', 'Export', 'Screen capture', 'Full screen', 'Save', 'Put away', 'Close into the fan']), items)
        await E(f'{D}.clickMenu("○ Keyboard")')
        f2 = await info('files')
        await E(f'{D}.clickMenu("x")')
        await E('''(() => { const t = window.__counter.find('files'); window.__counter.openTrayMenu(t, 400, 400); })()''')
        await E(f'''{D}.clickMenu([...document.querySelectorAll('.fc-menu button')].map(b=>b.textContent).find(x=>x.endsWith('Audio Mixer')))''')
        st = await E('''(() => { const t = window.__counter.find('files'); const m = t.stack.find(c => c.type === 'audio.mixer'); return {active: t.stack[t.active].type, lv: m.state.levels[2], mu: m.state.mute[3]}; })()''')
        check('switching stacked contents keeps each one\'s state', f2['active'] == 'Keyboard' and st == {'active': 'audio.mixer', 'lv': 0.11, 'mu': True}, [f2['active'], st])
        check('tray minimum comes from its largest content', f['min'] == {'w': 480, 'h': 170} and f['w'] >= 480 and f['h'] >= 170, [f['min'], f['w'], f['h']])

        # lock: a locked tray keeps its exact place and shape while another is dragged into it
        await E(f'window.__counter.lock(window.__counter.find("chat"), true)')
        before = await E('JSON.stringify(window.__counter.find("chat").q.map(p => p.map(v => +v.toFixed(2))))')
        c0 = await info('chat')
        r = await E(f'{D}.dragTo("tools", {c0["cx"]}, {c0["cy"]}, 260)')
        after = await E('JSON.stringify(window.__counter.find("chat").q.map(p => p.map(v => +v.toFixed(2))))')
        c1 = await info('chat')
        for _ in range(40): await E(f'{D}.step()')
        after2 = await E('JSON.stringify(window.__counter.find("chat").q.map(p => p.map(v => +v.toFixed(2))))')
        check('locked tray: not moved, dented or resized by a tray driven into it', before == after == after2 and (c0['cx'], c0['cy'], c0['w'], c0['h']) == (c1['cx'], c1['cy'], c1['w'], c1['h']), [c0['cx'], c0['cy'], c1['cx'], c1['cy']])
        pr = await E(f'{D}.pressure()')
        check('a tray driven into a locked one does not pass into it', pr['overlap'] <= 4.5, pr)
        r2 = await E(f'{D}.dragTo("chat", 900, 500, 50)')
        c2 = await info('chat')
        check('a locked tray cannot be dragged', (c2['cx'], c2['cy']) == (c1['cx'], c1['cy']), r2)
        sz = await E(f'{D}.sizeTo("chat", 600, 500, 20)')
        check('a locked tray cannot be resized', (sz['w'], sz['h']) == (c1['w'], c1['h']), sz)
        # its contents still work: a locked tray is not frozen inside
        clickable = await E('''(() => { const t = window.__counter.find('chat'); return getComputedStyle(t.el).pointerEvents; })()''')
        check('a locked tray\'s contents stay usable', clickable == 'auto', clickable)
        await E('window.__counter.lock(window.__counter.find("chat"), false)')
        r3 = await E(f'{D}.dragTo("chat", {c1["cx"] + 60}, {c1["cy"] - 40}, 120)')
        c3 = await info('chat')
        check('unlocked again, it moves', abs(c3['cx'] - c1['cx']) > 20, [c1['cx'], c3['cx']])

        # drag slowly through the crowd, from one side of the counter to the other
        o0 = await info('output')
        r = await E(f'{D}.dragTo("output", 600, 620, 900)')
        o1 = await info('output')
        pr = await E(f'{D}.pressure()')
        dist0 = ((o0['cx'] - 600) ** 2 + (o0['cy'] - 620) ** 2) ** 0.5
        dist1 = ((o1['cx'] - 600) ** 2 + (o1['cy'] - 620) ** 2) ** 0.5
        check('a tray can be dragged across a full counter (gets most of the way)', dist1 < 0.25 * dist0, [round(dist0), round(dist1), r])
        check('...without frames passing into each other', pr['overlap'] <= 5, pr)
        await pg.screenshot(path=f'{OUT}/v_after_drag.png')

        # resize keeps the shape
        t0 = await info('tools')
        q0 = await E('(() => { const t = window.__counter.find("tools"); return {fam: t.family, n: t.base.length}; })()')
        rs = await E(f'{D}.sizeTo("tools", {t0["w"] + 160}, {t0["h"] + 60}, 40)')
        q1 = await E('(() => { const t = window.__counter.find("tools"); return {fam: t.family, n: t.base.length}; })()')
        check('resizing changes size, not shape', q0 == q1 and rs['w'] > t0['w'] + 40, [q0, q1, t0['w'], rs])
        rs2 = await E(f'{D}.sizeTo("tools", 100, 100, 40)')
        check('resizing never goes below what the contents need', rs2['w'] >= t0['min']['w'] and rs2['h'] >= t0['min']['h'], [rs2, t0['min']])

        # reset
        await E('window.__counter.reset(window.__counter.find("tools"))')
        t2 = await info('tools')
        check('reset brings a tray back toward its own size', abs(t2['w'] - t2['natural']['w']) < 0.3 * t2['natural']['w'], [t2['w'], t2['natural']])

        # put away and bring back
        await E(f'{D}.setClock(100000)')
        await E('window.__counter.park(window.__counter.find("status"))')
        await E(f'{D}.setClock(101000)'); await E(f'{D}.step()')
        s1 = await info('status')
        dock = await E('[...document.querySelectorAll(".fc-dock")].map(d => d.textContent)')
        check('put away: tray leaves the counter, its tag shows in the side stack', s1['parked'] and s1['hidden'] and 'System Status' in dock, [s1, dock])
        await E('window.__counter.unpark(window.__counter.find("status"))')
        await E(f'{D}.setClock(102000)'); await E(f'{D}.step()')
        s2 = await info('status')
        check('brought back from the side stack', not s2['parked'] and not s2['hidden'], s2)

        # close into the fan and reopen from its blade
        await E('window.__counter.close(window.__counter.find("tools"))')
        await E(f'{D}.setClock(103000)'); await E(f'{D}.step()')
        t3 = await info('tools')
        blades = await E(f'{D}.blades()')
        check('close flies the tray into its fan blade (blade stays)', t3['closed'] and any(x['title'] == 'Tools' for x in blades), blades)
        await E('window.__counter.reopen(window.__counter.find("tools"))')
        await E(f'{D}.setClock(104000)'); await E(f'{D}.step()')
        t4 = await info('tools')
        check('reopen from the fan brings it back as it was', not t4['closed'] and not t4['hidden'] and t4['stack'] == t3['stack'], t4)

        # the New blade: picker with programs, rooms, blank, file
        await E('window.__counter.openPicker(null)')
        vi = await E(f'{D}.veilItems()')
        check('New opens a picker of programs, rooms, a blank tray and a file', all(any(v.startswith(x) for v in vi) for x in ['Live Preview', 'Control Room', 'Blank tray', 'A file from this computer…']), vi)
        await E(f'{D}.clickVeil("Blank tray")')
        await E(f'{D}.setClock(106000)'); await E(f'{D}.step()')
        trs = await E('window.__counter.trays.map(t => ({id: t.id, title: t.stack[t.active].title, hidden: !!t.hidden}))')
        blank = [t for t in trs if t['title'] == 'New Tray']
        check('a blank tray opens out of the fan', len(blank) == 1 and not blank[0]['hidden'], trs)
        bid = blank[0]['id']
        await E(f'window.__counter.importInto(window.__counter.find("{bid}"), "status.monitor")')
        bi = await info(bid)
        check('importing into a blank tray replaces the placeholder', bi['types'] == ['status.monitor'], bi)

        # import into a locked tray that is too small: the make-room question
        await E(f'window.__counter.lock(window.__counter.find("{bid}"), true)')
        await E(f'window.__counter.importInto(window.__counter.find("{bid}"), "page", {{url: "/static/gallery.html", title: "Gallery"}})')
        vi = await E(f'{D}.veilItems()')
        check('content too big for a locked tray asks to make room', vi == ['Make room', 'Open in a new tray', 'Cancel'], vi)
        await E(f'{D}.clickVeil("Make room")')
        for _ in range(140): await E(f'{D}.step()')
        bi2 = await info(bid)
        pr = await E(f'{D}.pressure()')
        check('make room never presses frames into each other', pr['overlap'] <= 4.6, pr)
        check('make room: the locked tray grows to fit (or shows its contents scaled to fit), stays locked',
              bi2['locked'] and bi2['w'] >= 420 and bi2['h'] >= 280 and 'Gallery' in bi2['stack'] and (bi2['cx'], bi2['cy']) != (0, 0), bi2)

        # full screen
        await E(f'window.__counter.fullScreen(window.__counter.find("preview"))')
        fs = await E('window.__counter.find("preview").el.classList.contains("fc-full")')
        await pg.keyboard.press('Escape')
        fs2 = await E('window.__counter.find("preview").el.classList.contains("fc-full")')
        check('full screen and back with Escape', fs and not fs2, [fs, fs2])

        # export
        async with pg.expect_download() as dl:
            await E('window.__counter.exportTray(window.__counter.find("files"))')
        d = await dl.value
        path = f'{OUT}/export.json'; await d.save_as(path)
        ex = json.load(open(path))
        check('export writes the content as a file', ex.get('kind') == 'foresight.content' and ex.get('type') in ('audio.mixer', 'input.keyboard', 'files.browser'), {k: ex[k] for k in ('kind', 'type', 'title')})

        # screen capture (headless has no screen sharing: the page's own fallback must still give a picture)
        async with pg.expect_download() as dl:
            await E('window.__counter.capture(window.__counter.find("output"))')
        d = await dl.value
        cap = f'{OUT}/capture.png'; await d.save_as(cap)
        import os
        check('screen capture saves a picture of the tray', os.path.getsize(cap) > 2000, os.path.getsize(cap))

        # save and restore across a reload
        snap = await E('JSON.stringify(window.__counter.serialize())')
        await E('window.__counter.saveNow()')
        state0 = json.loads(snap)
        await pg.goto(BASE + '?once=1&lamp=0.3')
        await pg.wait_for_function('window.__counter && window.__counter.gl.stoneReady === true', timeout=90000)
        snap2 = await E('JSON.stringify(window.__counter.serialize())')
        state1 = json.loads(snap2)
        same = [(a['id'], round(a['x']), round(a['y']), round(a['w']), round(a['h']), a['locked'], a['active'], len(a['contents'])) for a in state0['trays']] == \
               [(a['id'], round(a['x']), round(a['y']), round(a['w']), round(a['h']), a['locked'], a['active'], len(a['contents'])) for a in state1['trays']]
        check('save keeps every tray, place, size, lock and contents across a reload', same)
        mix = await E('''(() => { const t = window.__counter.find('files'); const m = t.stack.find(c => c.type === 'audio.mixer'); return [m.state.levels[2], m.state.mute[3]]; })()''')
        check('...and each content\'s own state', mix == [0.11, True], mix)
        await E(f'{D}.setClock(200000)')
        await E('window.__settle()'); await E(f'{D}.draw()')
        await pg.screenshot(path=f'{OUT}/v_restored.png')
        await E('localStorage.clear()')

        check('no page errors', not errs, errs[:5])
        await b.close()
    bad = [r for r in results if not r[1]]
    print(f'\n{len(results) - len(bad)}/{len(results)} passed')

asyncio.run(main())
