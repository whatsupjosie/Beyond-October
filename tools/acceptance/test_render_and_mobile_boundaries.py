"""Observed native-render boundary and mobile emulation, never physical-device proof."""
import json

from tests.test_production25d_browser import production_browser,production_server,wait_for_actors


def page_for(browser,base,token,**options):
    context=browser.new_context(**options)
    context.add_init_script('sessionStorage.setItem("pubcast_token",'+json.dumps(token)+');')
    page=context.new_page();page.goto(base+'/static/production25d.html')
    page.wait_for_function("document.documentElement.dataset.production25d==='ready'")
    return context,page


def test_observe_existing_renderer_at_requested_4k_canvas(production_server,production_browser,tmp_path):
    base,owner,_=production_server;context,page=page_for(production_browser,base,owner['access_token'])
    try:
        wait_for_actors(page)
        result=page.evaluate('''()=>{
          const R=PubCast25DRenderer,pkg=PubCast25D.PACKAGES.news;
          const target=document.createElement('canvas'),world=document.createElement('canvas');
          target.width=world.width=3840;target.height=world.height=2160;
          const bridge={has:id=>PubCastGLB.has('p25d-news-'+id),draw:(c,id,...rest)=>PubCastGLB.draw(c,'p25d-news-'+id,...rest)};
          R.renderCamera(target.getContext('2d'),pkg,pkg.cameras[0],{assets:{},performers:pkg.performers,avatarBridge:bridge},world,0);
          const c=target.getContext('2d');
          return {requested_canvas:[target.width,target.height],renderer_space:[R.W,R.H],
            alpha_inside_supported_frame:c.getImageData(1279,719,1,1).data[3],
            alpha_outside_supported_frame:c.getImageData(2000,1000,1,1).data[3],
            alpha_requested_far_corner:c.getImageData(3839,2159,1,1).data[3]};
        }''')
        assert result['renderer_space']==[1280,720] and result['alpha_inside_supported_frame']>0
        assert result['alpha_outside_supported_frame']==result['alpha_requested_far_corner']==0
        result['native_4k_gate']='FAIL_FIXED_720P_RENDER_SPACE_NOT_NATIVE_4K'
        (tmp_path/'renderer-probe.json').write_text(json.dumps(result,indent=2)+'\n')
    finally:context.close()


def test_mobile_viewport_touch_record_and_reload(production_server,production_browser,tmp_path):
    base,owner,_=production_server
    context,page=page_for(production_browser,base,owner['access_token'],viewport={'width':390,'height':844},is_mobile=True,has_touch=True,device_scale_factor=2)
    try:
        wait_for_actors(page)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.tap('#start');page.tap('#record')
        page.wait_for_function('PubCast25DStudio.state().journal?.chunks>=2',timeout=20000)
        page.tap('#recordStop');page.wait_for_function('!PubCast25DStudio.state().recording')
        page.tap('#stop');page.wait_for_function('!PubCast25DStudio.state().session')
        before=page.evaluate('async()=>(await PubCast25DStore.list())[0]')
        assert before['media']['bytes']>0 and not before['media']['incomplete']
        page.reload();page.wait_for_function("document.documentElement.dataset.production25d==='ready'")
        after=page.evaluate('async()=>(await PubCast25DStore.list())[0]')
        assert after['media']['id']==before['media']['id'] and after['media']['bytes']==before['media']['bytes']
        (tmp_path/'mobile-emulation.json').write_text(json.dumps({'viewport':[390,844],'touch_capture_reload':'PASS','recorded_bytes':after['media']['bytes'],'real_phone':'NOT_AVAILABLE','gpu':'SWIFTSHADER_SOFTWARE'},indent=2)+'\n')
    finally:context.close()
