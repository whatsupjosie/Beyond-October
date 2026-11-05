"""Actual GLB pixels remain identical while duplicate same-frame draws are avoided."""
from tests.test_production25d_browser import production_browser, production_server, studio, wait_for_actors


def test_preview_reuses_exact_pose_pixels_and_new_frames_still_render(studio):
    page, _ = studio
    wait_for_actors(page)
    result = page.evaluate("""async () => {
      const originals=[];
      let renders = 0;
      const id='frame-reuse-probe', make=()=>{
        const c=document.createElement('canvas');c.width=c.height=400;return c;
      };
      try {
        await PubCastGLB.load(id,'./world/test_avatars/MakeHuman_Female.glb','Frame reuse');
        for(const Type of [window.WebGLRenderingContext,window.WebGL2RenderingContext].filter(Boolean)) {
          for(const name of ['drawElements','drawArrays','drawElementsInstanced','drawArraysInstanced']) {
            const original=Type.prototype[name];if(!original)continue;
            originals.push([Type.prototype,name,original]);
            Type.prototype[name]=function(...args){renders++;return original.apply(this,args);};
          }
        }
        const a=make(), b=make(), c=make();
        PubCastGLB.draw(a.getContext('2d'),id,200,380,300,{dt:.1,cacheFrame:true,frameStamp:12345});
        const afterProgram=renders;
        PubCastGLB.draw(b.getContext('2d'),id,200,380,300,{dt:0,reuseFrame:true,frameStamp:12345});
        const afterPreview=renders;
        const x=a.getContext('2d').getImageData(0,0,400,400).data;
        const y=b.getContext('2d').getImageData(0,0,400,400).data;
        let differing=0;for(let i=0;i<x.length;i++)if(x[i]!==y[i])differing++;
        PubCastGLB.draw(c.getContext('2d'),id,200,380,300,{dt:0,reuseFrame:true,frameStamp:12346});
        return {afterProgram,afterPreview,afterNext:renders,differing};
      } finally { for(const [proto,name,original] of originals)proto[name]=original; PubCastGLB.clear(id); }
    }""")
    assert result['afterProgram'] > 0
    assert result['afterPreview'] == result['afterProgram']
    assert result['afterNext'] > result['afterPreview']
    assert result['differing'] == 0
    assert page.problems == []
