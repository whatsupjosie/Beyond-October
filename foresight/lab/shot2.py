import asyncio, sys
from playwright.async_api import async_playwright
async def main(out, theme, select='', wear='0', extra=''):
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
        pg = await b.new_page(viewport={'width':1600,'height':1000}); pg.set_default_timeout(300000)
        logs=[]; pg.on('console', lambda m: logs.append(m.type+': '+m.text) if m.type in ('error','warning') else None); pg.on('pageerror', lambda e: logs.append('pageerror: '+str(e)))
        await pg.goto(f'http://127.0.0.1:8781/foresight/lab/lab.html?once=1&theme={theme}&select={select}&wear={wear}{extra}')
        await pg.wait_for_function('window.__lab && (!G_STONE || G.stoneReady)') if False else None
        await pg.wait_for_function('typeof G !== "undefined" && G.stoneReady===true', timeout=60000)
        await pg.evaluate('window.__settle()')
        await pg.evaluate("document.querySelectorAll('video').forEach(v=>{v.pause(); v.currentTime=1.2;})")
        await pg.wait_for_timeout(500)
        await pg.evaluate('window.__draw()')
        await pg.wait_for_timeout(300)
        await pg.screenshot(path=out, timeout=300000)
        print(out, '\n'.join(logs[:8]))
        await b.close()
asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else '', sys.argv[4] if len(sys.argv) > 4 else '0', sys.argv[5] if len(sys.argv) > 5 else ''))
