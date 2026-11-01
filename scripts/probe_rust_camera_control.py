#!/usr/bin/env python3
import argparse, asyncio, json, time, uuid
import websockets
P="pubcast.camera.control.v1"
async def main(url,token):
  async with websockets.connect(url) as ws:
    rev=time.time_ns() & ((1<<63)-1)
    async def call(action,**kw):
      nonlocal rev; rev+=1; rid=uuid.uuid4().hex
      msg={"protocol":P,"token":token,"request_id":rid,"action":action,"timestamp":time.time(),**kw}
      await ws.send(json.dumps(msg)); ack=json.loads(await ws.recv())
      assert ack.get("request_id")==rid and ack.get("protocol")==P, ack
      assert ack.get("ok") is True, ack
      assert ack.get("frame_path_proven") is False, "Stage-1 receiver must not claim frame proof"
      return ack
    await call("hello")
    for cid,x in (("rust_cam_1",0.0),("rust_cam_2",2.0)):
      await call("register",camera_id=cid,revision=rev,name=cid,position=[x,1.65,4.0],rotation=[0,180,0],fov=50)
    await call("set_mode",camera_id="rust_cam_1",revision=rev,mode="Program")
    await call("set_mode",camera_id="rust_cam_2",revision=rev,mode="Preview")
    await call("update_pose",camera_id="rust_cam_2",revision=rev,position=[2.2,1.7,4.1],rotation=[0,175,0],fov=45)
    print("PASS: authenticated two-camera Stage-1 control; frame_path_proven=false")
if __name__=="__main__":
  ap=argparse.ArgumentParser(); ap.add_argument("--url",default="ws://127.0.0.1:8765"); ap.add_argument("--token",required=True); a=ap.parse_args(); asyncio.run(main(a.url,a.token))
