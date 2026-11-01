"""Real Chromium/Reach smoke: Foresight -> 2i and Pub Partner trays.

Run with Reach listening at PUBCAST_TEST_BASE (default http://127.0.0.1:8000).
No model credentials required; a live AI response is deliberately NOT certified.
"""
import asyncio
import os
from playwright.async_api import async_playwright

BASE = os.getenv('PUBCAST_TEST_BASE', 'http://127.0.0.1:8000').rstrip('/')


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
        page = await browser.new_page(viewport={'width': 1440, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            response = await page.goto(BASE + '/foresight-counter?fresh=1', wait_until='domcontentloaded', timeout=45000)
            assert response and response.status == 200, 'Foresight did not load'
            await page.wait_for_function('window.__counter && window.__programs', timeout=60000)
            count = await page.evaluate('window.__counter.trays.length')
            assert count == 0, f'Fresh Counter unexpectedly has {count} trays'
            for program, expected in [('twoi', '/writers-room'), ('pubpartner_workspace', '/pubpartner')]:
                await page.evaluate('(id) => window.__programs.open(id, {})', program)
                await page.wait_for_function('([path]) => [...document.querySelectorAll("iframe")].some(f => f.getAttribute("src")?.includes(path))', [expected], timeout=30000)
                frame = next((f for f in page.frames if expected in f.url), None)
                if frame is None:
                    await page.wait_for_timeout(2000)
                    frame = next((f for f in page.frames if expected in f.url), None)
                assert frame is not None, f'{program} iframe never navigated to {expected}'
                assert await frame.locator('body').count(), f'{program} frame has no document body'
                print('PASS: opened', program, 'in live Counter')
            assert not errors, 'Counter page JavaScript errors: ' + repr(errors)
            print('PASS: blank Counter, real 2i and Pub Partner tray navigation')
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
