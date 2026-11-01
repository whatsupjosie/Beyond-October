import asyncio, sys
from playwright.async_api import async_playwright
async def main(theme):
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist'])
        pg = await b.new_page(viewport={'width':1600,'height':1000}); pg.set_default_timeout(300000)
        await pg.goto(f'http://127.0.0.1:8781/foresight/lab/lab.html?once=1&theme={theme}&select=tools')
        await pg.evaluate('window.__settle()')
        await pg.evaluate("document.querySelectorAll('video').forEach(v=>{v.pause(); v.currentTime=1.2;})")
        path = [None,(1120,700),(1000,640),(900,600)]
        for i,pt in enumerate(path):
            if pt:
                x,y = pt
                await pg.evaluate(f"""(()=>{{ const L=window.__lab; const t=L.trays.find(t=>t.id==='tools'); t.pinned=true;
                  const tx={x}, ty={y}, steps=30, sx=t.cx, sy=t.cy;
                  for(let k=1;k<=steps;k++){{ const save=L.trays.map(q=>[q.cx,q.cy]); t.cx=sx+(tx-sx)*k/steps; t.cy=sy+(ty-sy)*k/steps;
                    const r=window.__solveOnce(); if(!r.valid && !r.easing){{ L.trays.forEach((q,j)=>{{q.cx=save[j][0];q.cy=save[j][1];}}); window.__solveOnce(); break; }} }}
                  for(let k=0;k<8;k++) window.__solveOnce(); }})()""")
            await pg.evaluate('window.__draw()')
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=f'm2_{i}.png')
        await b.close()
asyncio.run(main(sys.argv[1]))
