"""Exercise camera-compute feasibility without changing production behavior.

Run with the project's Python environment; Chromium/Playwright must be installed.
Output is evidence, including expected failures, not a production readiness badge.
The server uses disposable data. Render instrumentation affects one test page only.
"""
from __future__ import annotations

import argparse
import asyncio
import gc
import hashlib
import importlib.util
import io
import json
import logging
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def free_port():
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def node_probe():
    from modules.bridge_raw import MessageType
    from modules.evo.distributed_engine import (
        DistributedEngineNode, EngineConfig, EngineMode, WorkUnit,
    )
    primary_port, camera_port = free_port(), free_port()
    primary = DistributedEngineNode(EngineConfig(
        engine_id="audit-primary", mode=EngineMode.TWIN,
        primary_port=primary_port, listen_port=camera_port,
        heartbeat_interval=.05, health_check_interval=.05,
    ))
    camera = DistributedEngineNode(EngineConfig(
        engine_id="audit-camera", mode=EngineMode.CAMERA,
        primary_port=primary_port, listen_port=camera_port,
        heartbeat_interval=.05, health_check_interval=.05,
    ))
    completed = []
    camera.on_work_complete(completed.append)
    output = {}
    messages = io.StringIO()
    handler = logging.StreamHandler(messages)
    logger = logging.getLogger("modules.bridge_raw")
    old_level = logger.level
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        await primary.start()
        await camera.start()
        for _ in range(30):
            if "audit-camera" in primary._connected_nodes:
                break
            await asyncio.sleep(.02)
        output["heartbeat_received"] = "audit-camera" in primary._connected_nodes
        try:
            primary.distribute_work(WorkUnit("public-dispatch", "video_encode", data=b"frame"), "audit-camera")
            output["public_dispatch_error"] = None
        except Exception as exc:
            output["public_dispatch_error"] = f"{type(exc).__name__}: {exc}"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            output["typed_datagram_sent"] = primary.bridge.send(MessageType.PROCESS_WORK, {
                "target": "audit-camera", "work": {
                    "work_id": "typed-dispatch", "work_type": "video_encode", "data": "6672616d65",
                },
            })
            await asyncio.sleep(.3)
            gc.collect()
            output["typed_job_completions"] = len(completed)
            output["warnings"] = [str(item.message) for item in caught]
        output["bridge_errors"] = messages.getvalue().splitlines()
        # Exercise the actual handlers, with two different inputs, to distinguish
        # processing from successful transport/control state.
        output["processor_outputs"] = {}
        for kind in ("voxel_render", "mesh_generate", "audio_process", "video_encode"):
            results = []
            for value in (b"first source", b"different source"):
                work = WorkUnit("local-" + kind, kind, data=value)
                await camera._process_work(work)
                results.append({"completed": work.completed, "result": work.result.decode(), "error": work.error})
            output["processor_outputs"][kind] = results
    finally:
        await camera.stop()
        await primary.stop()
        logger.removeHandler(handler)
        logger.setLevel(old_level)
    return output


INSTRUMENT = """() => {
 const target=PubCast25DRenderer, original=target.renderCamera;
 const audit=window.__cameraComputeAudit={skipPreview:false,calls:{},skipped:0};
 target.renderCamera=function(ctx,...args){
   const name=ctx.canvas.id;
   if(audit.skipPreview && name==='preview'){audit.skipped++;return;}
   const start=performance.now();
   const result=original.call(this,ctx,...args);
   const item=audit.calls[name]||(audit.calls[name]={count:0,wallMs:0});
   item.count++; item.wallMs+=performance.now()-start;
   return result;
 };
 audit.restore=()=>{target.renderCamera=original;};
 return {studio:PubCast25DStudio.state(),shots:PubCast25D.PACKAGES.news.cameras.map(c=>c.id),
   worker:typeof Worker,offscreenCanvas:typeof OffscreenCanvas};
}"""

WORKER_PROBE = """async () => {
 // A real, bounded background production task using actual program pixels.
 // This is an isolated feasibility probe, NOT an integrated camera/Twin worker.
 const code=`self.onmessage=async ({data})=>{try{
   const c=new OffscreenCanvas(320,180),ctx=c.getContext('2d');
   ctx.imageSmoothingEnabled=false;ctx.drawImage(data.image,0,0,320,180);data.image.close();
   const rgba=ctx.getImageData(0,0,320,180).data.buffer;
   const png=await (await c.convertToBlob({type:'image/png'})).arrayBuffer();
   postMessage({rgba,png},[rgba,png]);
 }catch(e){postMessage({error:String(e)});}};`;
 const url=URL.createObjectURL(new Blob([code],{type:'text/javascript'}));
 const worker=new Worker(url), program=document.querySelector('#program');
 const reference=document.createElement('canvas');reference.width=320;reference.height=180;
 const ctx=reference.getContext('2d');ctx.imageSmoothingEnabled=false;
 let bytes=0,matches=0;const started=performance.now();
 const before=__cameraComputeAudit.calls.program.count;
 try{
   for(let i=0;i<12;i++){
     const image=await createImageBitmap(program);
     ctx.clearRect(0,0,320,180);ctx.drawImage(image,0,0,320,180);
     const expected=ctx.getImageData(0,0,320,180).data;
     const result=await new Promise((resolve,reject)=>{
       const timer=setTimeout(()=>reject(Error('worker timeout')),5000);
       worker.onmessage=e=>{clearTimeout(timer);resolve(e.data);};
       worker.onerror=e=>{clearTimeout(timer);reject(Error(e.message));};
       worker.postMessage({image},[image]);
     });
     if(result.error)throw Error(result.error);
     const actual=new Uint8ClampedArray(result.rgba);
     if(actual.length===expected.length&&actual.every((v,j)=>v===expected[j]))matches++;
     bytes+=result.png.byteLength;
     await new Promise(requestAnimationFrame);
   }
   return {jobs:12,pixelExactJobs:matches,encodedPngBytes:bytes,wallMs:performance.now()-started,
     programFramesDuringWork:__cameraComputeAudit.calls.program.count-before,
     integration:'probe-only worker; not attached to Twin or CameraBoxer'};
 }finally{worker.terminate();URL.revokeObjectURL(url);}
}"""


def browser_probe():
    # Reuse the real authenticated-server/browser setup used by acceptance tests.
    spec = importlib.util.spec_from_file_location("studio_acceptance", ROOT / "tests/test_production25d_browser.py")
    acceptance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(acceptance)

    class TempFactory:
        def __init__(self, root):
            self.root = root

        def mktemp(self, name):
            path = self.root / name
            path.mkdir()
            return path

    with tempfile.TemporaryDirectory(prefix="pubcast-camera-audit-") as temp:
        server = acceptance.production_server.__wrapped__(TempFactory(Path(temp)))
        browser = acceptance.production_browser.__wrapped__()
        try:
            base, auth, api = next(server)
            chromium = next(browser)
            context = chromium.new_context(viewport={"width": 1440, "height": 1000})
            context.add_init_script("sessionStorage.setItem('pubcast_token'," + json.dumps(auth["access_token"]) + ");"
                                    "sessionStorage.setItem('pubcast_user'," + json.dumps(json.dumps({"username": "engineer", "role": "owner"})) + ");")
            page = context.new_page()
            page_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(base + "/static/production25d.html")
            page.wait_for_function("document.documentElement.dataset.production25d === 'ready'")
            acceptance.wait_for_actors(page)
            page.evaluate("PubCast25DStudio.startProduction()")
            page.wait_for_function("document.querySelector('#switcherLink').textContent === 'VIDEO: SHARED SWITCHER'")
            page.wait_for_timeout(500)
            output = {"environment": {"browser": chromium.version, "gpu": "SwiftShader (software), not owner hardware"},
                      "initial": page.evaluate(INSTRUMENT), "phases": []}
            headers = {"Authorization": "Bearer " + auth["access_token"]}
            for name, skip in (("baseline", False), ("boxer_tier3", False), ("probe_skip_preview", True), ("restored", False)):
                if name == "boxer_tier3":
                    response = api.post("/api/boxer/override", json={"tier": "tier_3"}, headers=headers)
                    response.raise_for_status()
                    output["boxer_tier3"] = api.get("/api/boxer/status", headers=headers).json()
                elif name == "probe_skip_preview":
                    response = api.post("/api/boxer/override", json={"tier": "auto"}, headers=headers)
                    response.raise_for_status()
                page.evaluate("skip=>{const a=__cameraComputeAudit;a.skipPreview=skip;a.calls={};a.skipped=0;a.started=performance.now();}", skip)
                page.wait_for_timeout(2500)
                result = page.evaluate("()=>{const a=__cameraComputeAudit;return {calls:a.calls,skipped:a.skipped,wallMs:performance.now()-a.started};}")
                output["phases"].append({"name": name, **result})
            output["background_frame_worker"] = page.evaluate(WORKER_PROBE)
            output["canonical_sources"] = api.get("/api/cameras", headers=headers).json()
            output["page_errors"] = page_errors
            page.evaluate("__cameraComputeAudit.restore()")
            page.evaluate("PubCast25DStudio.stopProduction()")
            context.close()
            return output
        finally:
            browser.close()
            server.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    output = {"source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "node_probe": asyncio.run(node_probe()), "browser_probe": browser_probe()}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"evidence": str(args.out), "heartbeat": output["node_probe"]["heartbeat_received"],
                      "dispatch_error": output["node_probe"]["public_dispatch_error"],
                      "typed_jobs_completed": output["node_probe"]["typed_job_completions"],
                      "browser_errors": output["browser_probe"]["page_errors"],
                      "background_frame_worker": output["browser_probe"]["background_frame_worker"]}, indent=2))


if __name__ == "__main__":
    main()
