"""Build two free (CC0) rigged MakeHuman humans and export each as GLB, FBX and OBJ.

Run with the Blender-as-module Python: python build_test_humans.py OUT_DIR
Variants deliberately cover real-world import problems:
  male:   GLB metres, FBX metres,          OBJ Y-up
  female: GLB metres, FBX centimetres x100, OBJ Z-up (lying on its back)
"""
import math
import os
import sys

import bpy  # must load before addon_utils exists
import addon_utils  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[-1])
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(HERE, "mpfb2/src"))
home = os.path.join(HERE, "mpfb_user")
os.makedirs(home, exist_ok=True)
bpy.utils.extension_path_user = lambda pkg, path="", create=False: (os.path.join(home, path) if path else home)
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("mpfb", default_set=True, persistent=False)

from mpfb.services.humanservice import HumanService  # noqa: E402
from mpfb.services.targetservice import TargetService  # noqa: E402


def clear():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.actions, bpy.data.images):
        for item in list(coll):
            if item.users == 0:
                coll.remove(item)


def skin_material(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.55
    return mat


def build(gender: float, rgb):
    clear()
    macros = TargetService.get_default_macro_info_dict()
    macros["gender"] = gender
    macros["muscle"] = 0.55
    human = HumanService.create_human(scale=0.1, macro_detail_dict=macros)
    # The skeleton is fitted from the helper geometry, so rig first.
    HumanService.add_builtin_rig(human, "mixamo", import_weights=True)
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    bpy.ops.object.select_all(action="DESELECT")
    human.select_set(True)
    bpy.context.view_layer.objects.active = human
    # Bake the body shape into the mesh, then drop the hidden helper geometry.
    if human.data.shape_keys:
        bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
    for mod in list(human.modifiers):
        if mod.type == "MASK":
            bpy.ops.object.modifier_apply(modifier=mod.name)
    human.data.materials.clear()
    human.data.materials.append(skin_material(f"skin_{gender}", rgb))
    return human, rig


def add_wave(rig):
    """A two-second idle sway with a wave, keyed on standard Mixamo bones."""
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    action = bpy.data.actions.new("Wave")
    rig.animation_data_create().action = action
    bones = rig.pose.bones
    names = {b.name.split(":")[-1]: b for b in bones}
    arm = names.get("RightArm")
    fore = names.get("RightForeArm")
    spine = names.get("Spine")
    for frame, (a, f, s) in {1: (0, 0, 0), 15: (-70, -30, 3), 30: (-70, 30, -3), 45: (-70, -30, 3), 60: (0, 0, 0)}.items():
        for bone, deg, axis in ((arm, a, 1), (fore, f, 2), (spine, s, 2)):
            if bone is None:
                continue
            bone.rotation_mode = "XYZ"
            rot = [0.0, 0.0, 0.0]
            rot[axis] = math.radians(deg)
            bone.rotation_euler = rot
            bone.keyframe_insert("rotation_euler", frame=frame)
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, 60
    bpy.ops.object.mode_set(mode="OBJECT")


def measure(obj):
    import mathutils
    zs = [(obj.matrix_world @ mathutils.Vector(c)).z for c in obj.bound_box]
    return max(zs) - min(zs)


def export(name, human, rig, *, fbx_scale, obj_up):
    print(name, "height m:", round(measure(human), 3), "bones:", len(rig.data.bones), "verts:", len(human.data.vertices))
    bpy.ops.object.select_all(action="DESELECT")
    human.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, f"{name}.glb"), export_format="GLB",
                              use_selection=True, export_animations=True, export_skins=True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, f"{name}.fbx"), use_selection=True,
                             object_types={"ARMATURE", "MESH"}, global_scale=fbx_scale,
                             apply_unit_scale=True, add_leaf_bones=False, bake_anim=True,
                             path_mode="COPY", embed_textures=True)
    bpy.ops.object.select_all(action="DESELECT")
    human.select_set(True)
    bpy.context.view_layer.objects.active = human
    bpy.ops.wm.obj_export(filepath=os.path.join(OUT, f"{name}.obj"), export_selected_objects=True,
                          up_axis=obj_up, forward_axis="NEGATIVE_Z" if obj_up == "Y" else "Y",
                          export_materials=True, path_mode="COPY", apply_modifiers=True)


for name, gender, fbx_scale, obj_up, rgb in (("mh_male", 1.0, 1.0, "Y", (0.62, 0.42, 0.30)), ("mh_female", 0.0, 100.0, "Z", (0.86, 0.66, 0.55))):
    human, rig = build(gender, rgb)
    add_wave(rig)
    export(name, human, rig, fbx_scale=fbx_scale, obj_up=obj_up)

print("files:", sorted(os.listdir(OUT)))
