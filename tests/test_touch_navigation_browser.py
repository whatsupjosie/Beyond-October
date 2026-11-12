"""Real Chromium native touch and remote mouse-drag scrolling on real host pages."""
import json
import time
import pytest
from tests.test_production25d_browser import production_browser, production_server


@pytest.mark.parametrize('path', ['/static/human_profile.html?onboarding=1', '/static/production25d.html'])
def test_native_swipe_and_remote_background_drag_scroll(production_server, production_browser, path):
    base, auth, _ = production_server
    context = production_browser.new_context(viewport={'width':390,'height':740}, has_touch=True, is_mobile=True)
    try:
        context.add_init_script("sessionStorage.setItem('pubcast_token',"+json.dumps(auth['access_token'])+");")
        page=context.new_page(); errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(base+path)
        if 'human_profile' in path:
            page.wait_for_selector('#editor:not([hidden])')
        else:
            page.wait_for_function("document.documentElement.dataset.production25d==='ready'")
        session=context.new_cdp_session(page)
        session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':8,'y':600}]})
        for y in range(580,199,-20):
            session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':8,'y':y}]})
            time.sleep(.016)
        session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
        page.wait_for_function('window.scrollY > 100')
        assert page.evaluate("!document.documentElement.classList.contains('drag-scroll-active')")
        # Stop native momentum before testing the separate mouse-only fallback.
        page.wait_for_timeout(600)
        page.evaluate('window.scrollTo(0,0)')
        page.mouse.move(8,600);page.mouse.down();page.mouse.move(8,250,steps=15);page.mouse.up()
        assert page.evaluate('window.scrollY') > 100
        assert page.evaluate("!document.documentElement.classList.contains('drag-scroll-active')")
        if 'human_profile' in path:
            page.locator('#displayName').scroll_into_view_if_needed()
            box=page.locator('#displayName').bounding_box()
            page.mouse.move(box['x']+20,box['y']+20);page.mouse.down()
            assert page.evaluate("!document.documentElement.classList.contains('drag-scroll-active')")
            page.mouse.move(box['x']+80,box['y']+20,steps=5);page.mouse.up()
            page.locator('#displayName').fill('Touch test')
            assert page.locator('#displayName').input_value()=='Touch test'
        assert not errors, errors
    finally:
        context.close()
