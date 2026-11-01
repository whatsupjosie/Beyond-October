"""PubCast GLB skeleton/animation semantic adapter.
Maps imported GLB bone names to PubCast canonical performer commands.
Generated from recovered PubCast rig + MocapRetargeter contracts.
It deliberately refuses to guess unknown bones.
"""
import re

CANONICAL = ['Root', 'Pelvis', 'Spine_01', 'Spine_02', 'Spine_03', 'Neck_01', 'Head', 'Clavicle_L', 'UpperArm_L', 'UpperArm_Twist_L', 'LowerArm_L', 'LowerArm_Twist_L', 'Hand_L', 'Clavicle_R', 'UpperArm_R', 'UpperArm_Twist_R', 'LowerArm_R', 'LowerArm_Twist_R', 'Hand_R', 'Thigh_L', 'Thigh_Twist_L', 'Calf_L', 'Foot_L', 'Ball_L', 'Toe_L', 'Thigh_R', 'Thigh_Twist_R', 'Calf_R', 'Foot_R', 'Ball_R', 'Toe_R', 'Jaw']
ALIASES = {'rootjoint': 'Root', 'gltfcreatedrootjoint': 'Root', 'root': 'Root', 'hips': 'Pelvis', 'pelvis': 'Pelvis', 'spine': 'Spine_01', 'spine01': 'Spine_01', 'spine1': 'Spine_02', 'spine02': 'Spine_02', 'spine2': 'Spine_03', 'spine03': 'Spine_03', 'spline': 'Spine_03', 'neck': 'Neck_01', 'neck01': 'Neck_01', 'head': 'Head', 'jaw': 'Jaw', 'leftshoulder': 'Clavicle_L', 'claviclel': 'Clavicle_L', 'leftarm': 'UpperArm_L', 'upperarml': 'UpperArm_L', 'leftforearm': 'LowerArm_L', 'lowerarml': 'LowerArm_L', 'lefthand': 'Hand_L', 'handl': 'Hand_L', 'rightshoulder': 'Clavicle_R', 'clavicler': 'Clavicle_R', 'rightarm': 'UpperArm_R', 'upperarmr': 'UpperArm_R', 'rightforearm': 'LowerArm_R', 'lowerarmr': 'LowerArm_R', 'righthand': 'Hand_R', 'handr': 'Hand_R', 'leftupleg': 'Thigh_L', 'thighl': 'Thigh_L', 'leftleg': 'Calf_L', 'calfl': 'Calf_L', 'leftfoot': 'Foot_L', 'footl': 'Foot_L', 'lefttoebase': 'Toe_L', 'toel': 'Toe_L', 'rightupleg': 'Thigh_R', 'thighr': 'Thigh_R', 'rightleg': 'Calf_R', 'calfr': 'Calf_R', 'rightfoot': 'Foot_R', 'footr': 'Foot_R', 'righttoebase': 'Toe_R', 'toer': 'Toe_R'}

def normalize_bone_name(name):
    name = name.replace("mixamorig:", "")
    name = re.sub(r"_0?\\d+$", "", name)
    return re.sub(r"[^a-z0-9]", "", name.lower())

def to_pubcast_bone(name):
    key = normalize_bone_name(name)
    if key in ALIASES:
        return ALIASES[key]
    for canonical in CANONICAL:
        if normalize_bone_name(canonical) == key:
            return canonical
    m = re.match(r"(left|right)hand(thumb|index|middle|ring|pinky)([1-4])", key)
    if m:
        side = "L" if m.group(1) == "left" else "R"
        return f"{m.group(2).title()}_{int(m.group(3)):02d}_{side}"
    return None

def adapt_animation_targets(channels):
    """Return animation channels addressed to canonical PubCast bones.
    Unknown targets are reported, never silently redirected.
    """
    adapted, rejected = [], []
    for channel in channels:
        target = to_pubcast_bone(channel["bone"])
        if target is None:
            rejected.append(channel)
        else:
            item = dict(channel)
            item["source_bone"] = item["bone"]
            item["bone"] = target
            adapted.append(item)
    return adapted, rejected
