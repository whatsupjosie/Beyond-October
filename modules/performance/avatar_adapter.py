from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

CANONICAL_ALIASES={
 "pelvis":"hips","hip":"hips","hips":"hips","spine":"spine","chest":"chest","neck":"neck","head":"head",
 "left_shoulder":"left_shoulder","left_elbow":"left_elbow","left_wrist":"left_wrist","left_hand":"left_hand",
 "right_shoulder":"right_shoulder","right_elbow":"right_elbow","right_wrist":"right_wrist","right_hand":"right_hand",
 "left_hip":"left_hip","left_knee":"left_knee","left_ankle":"left_ankle","left_foot":"left_foot",
 "right_hip":"right_hip","right_knee":"right_knee","right_ankle":"right_ankle","right_foot":"right_foot",
}
# Common MediaPipe landmark indexes -> canonical names.
MEDIAPIPE={0:"head",11:"left_shoulder",12:"right_shoulder",13:"left_elbow",14:"right_elbow",15:"left_wrist",16:"right_wrist",
           23:"left_hip",24:"right_hip",25:"left_knee",26:"right_knee",27:"left_ankle",28:"right_ankle",31:"left_foot",32:"right_foot"}

@dataclass
class CanonicalPerformancePacket:
    avatar_id:str
    timestamp:float
    frame_index:int
    joints:Dict[str,Dict[str,Any]]
    blendshapes:Dict[str,float]=field(default_factory=dict)
    source:str="unknown"
    global_confidence:float=1.0

class AvatarPerformanceAdapter:
    """Normalize capture separately from avatar-specific retarget/rendering."""
    DEFAULT_AVATAR_OFFSETS = {"lumen": 1.35}
    def __init__(self, *, vertical_offset_m:float=0.0, avatar_offsets:Optional[Mapping[str,float]]=None):
        self.vertical_offset_m=float(vertical_offset_m)
        self.avatar_offsets=dict(self.DEFAULT_AVATAR_OFFSETS)
        if avatar_offsets:
            self.avatar_offsets.update({str(k).casefold():float(v) for k,v in avatar_offsets.items()})

    @staticmethod
    def _point(v:Any)->dict:
        if hasattr(v,"x"): return {"x":float(v.x),"y":float(v.y),"z":float(v.z),"confidence":float(getattr(v,"confidence",1.0))}
        if isinstance(v,Mapping):
            return {"x":float(v.get("x",0)),"y":float(v.get("y",0)),"z":float(v.get("z",0)),"confidence":float(v.get("confidence",v.get("visibility",1.0)))}
        if isinstance(v,(list,tuple)) and len(v)>=3: return {"x":float(v[0]),"y":float(v[1]),"z":float(v[2]),"confidence":float(v[3]) if len(v)>3 else 1.0}
        raise ValueError("unsupported joint point")

    def normalize(self,data:Any,*,avatar_id:str="avatar",source:str="auto",frame_index:int=0,timestamp:Optional[float]=None)->CanonicalPerformancePacket:
        if hasattr(data,"joints"):
            raw=data.joints; source = source if source!="auto" else "pubcast_mocap"
            timestamp = timestamp or (float(getattr(data,"timestamp",0))/1000.0 if getattr(data,"timestamp",0)>1e11 else float(getattr(data,"timestamp",0) or time.time()))
            frame_index=int(getattr(data,"frame_number",frame_index) or frame_index)
            face=getattr(data,"face",None) or {}
        elif isinstance(data,Mapping):
            raw=data.get("joints") or data.get("landmarks") or data.get("pose_landmarks") or {}
            face=data.get("blendshapes") or data.get("face") or {}
            timestamp=timestamp or float(data.get("timestamp") or data.get("t") or time.time())
            frame_index=int(data.get("frame_index") or data.get("frameNumber") or frame_index)
            if source=="auto": source=str(data.get("source") or "mapping")
        else: raise ValueError("unsupported performance packet")
        joints:Dict[str,dict]={}
        if isinstance(raw,(list,tuple)):
            iterable=((MEDIAPIPE.get(i),v) for i,v in enumerate(raw))
        else: iterable=((CANONICAL_ALIASES.get(str(k).lower(),str(k)),v) for k,v in raw.items())
        y_offset = self.vertical_offset_m + self.avatar_offsets.get(str(avatar_id).casefold(), 0.0)
        for name,v in iterable:
            if not name: continue
            p=self._point(v); p["y"] += y_offset; joints[name]=p
        # Derive pelvis midpoint when the tracker supplies hips but not pelvis.
        if "hips" not in joints and "left_hip" in joints and "right_hip" in joints:
            a,b=joints["left_hip"],joints["right_hip"]
            joints["hips"]={k:(a[k]+b[k])/2.0 for k in ("x","y","z","confidence")}
        bs:Dict[str,float]={}
        if isinstance(face,Mapping):
            for k,v in face.items():
                try: bs[str(k)]=max(0.0,min(1.0,float(v.get("score",v.get("value",0))) if isinstance(v,Mapping) else float(v)))
                except (TypeError,ValueError): pass
        conf=sum((j["confidence"] for j in joints.values()),0.0)/max(1,len(joints))
        return CanonicalPerformancePacket(avatar_id=avatar_id,timestamp=float(timestamp or time.time()),frame_index=frame_index,joints=joints,blendshapes=bs,source=source,global_confidence=conf)

    def to_precision_frame(self, packet:CanonicalPerformancePacket):
        """Convert the capture-neutral packet to the existing performer contract."""
        import numpy as np
        from modules.avatar_performer import PrecisionMocapFrame, JointPose, Quaternion
        poses={}
        for name,j in packet.joints.items():
            poses[name]=JointPose(
                position=np.array([j["x"],j["y"],j["z"]],dtype=np.float64),
                rotation=Quaternion.identity(),
                confidence=float(j.get("confidence",1.0)),
            )
        return PrecisionMocapFrame(avatar_id=packet.avatar_id,timestamp=packet.timestamp,frame_index=packet.frame_index,
            joint_poses=poses,blendshapes=dict(packet.blendshapes),global_confidence=packet.global_confidence)

    async def route_to_manager(self, data:Any, manager:Any, *, avatar_id:str, preset:str="MANNY", source:str="auto") -> CanonicalPerformancePacket:
        packet=self.normalize(data,avatar_id=avatar_id,source=source)
        if manager.get_performer(avatar_id) is None:
            if getattr(manager,"_streamer",None) is None:
                raise RuntimeError("avatar performer manager has not started")
            manager.create_performer(avatar_id,preset=preset)
        await manager.route_frame(self.to_precision_frame(packet))
        return packet
