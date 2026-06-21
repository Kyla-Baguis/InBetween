"""
MERCURY - Blender 5.1 compatible
Texture from C:\\Users\\ClearBug\\Downloads\\textures

HOW TO USE:
    1. Open this file in Blender Text Editor (Scripting tab)
    2. Press Run Script or Alt+P
    3. Press NUMPAD 0 to view through camera, SPACE to play
"""

import bpy
import math
from bpy_extras import anim_utils

TEXTURES = r"C:\Users\ClearBug\Downloads\textures"
FPS = 24
FRAMES = 250


# ------------------------------------------------------------------ UTILITIES

def reset():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for b in bpy.data.meshes:
        bpy.data.meshes.remove(b)
    for b in bpy.data.materials:
        bpy.data.materials.remove(b)
    for b in bpy.data.images:
        bpy.data.images.remove(b)
    s = bpy.context.scene
    s.frame_start = 1
    s.frame_end = FRAMES
    s.render.fps = FPS
    s.render.resolution_x = 1920
    s.render.resolution_y = 1080


def tex(filename):
    try:
        return bpy.data.images.load(TEXTURES + "\\" + filename)
    except Exception:
        print("WARNING: Not found: " + filename)
        return None


def sphere(name, r, loc=(0, 0, 0), segs=64):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segs, ring_count=segs // 2, radius=r, location=loc)
    o = bpy.context.active_object
    o.name = name
    bpy.ops.object.shade_smooth()
    return o


def mat_diffuse(name, img_file, roughness=0.8, col=(0.5, 0.5, 0.5, 1)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    N = m.node_tree.nodes
    L = m.node_tree.links
    N.clear()
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    tx = N.new("ShaderNodeTexImage")
    i = tex(img_file)
    if i:
        tx.image = i
    pr = N.new("ShaderNodeBsdfPrincipled")
    pr.inputs["Base Color"].default_value = col
    pr.inputs["Roughness"].default_value = roughness
    ou = N.new("ShaderNodeOutputMaterial")
    L.new(tc.outputs["UV"], mp.inputs["Vector"])
    L.new(mp.outputs["Vector"], tx.inputs["Vector"])
    if i:
        L.new(tx.outputs["Color"], pr.inputs["Base Color"])
    L.new(pr.outputs["BSDF"], ou.inputs["Surface"])
    return m


def set_linear_fcurves(obj):
    action = obj.animation_data.action
    action_slot = obj.animation_data.action_slot
    channelbag = anim_utils.action_get_channelbag_for_slot(action, action_slot)
    if channelbag:
        for fc in channelbag.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


def add_spin(obj, tilt_deg, frames=FRAMES, retrograde=False):
    d = -1 if retrograde else 1
    tx = math.radians(tilt_deg)
    obj.rotation_mode = 'XYZ'
    obj.rotation_euler = (tx, 0, 0)
    obj.keyframe_insert(data_path="rotation_euler", frame=1)
    obj.rotation_euler = (tx, 0, d * math.radians(360))
    obj.keyframe_insert(data_path="rotation_euler", frame=frames)
    set_linear_fcurves(obj)


def set_black_world():
    w = bpy.data.worlds["World"]
    w.use_nodes = True
    N = w.node_tree.nodes
    bg = N.get("Background") or N.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0, 0, 0, 1)
    bg.inputs["Strength"].default_value = 0


def make_camera(loc, rot_x_deg, lens=50):
    for o in list(bpy.data.objects):
        if o.type == 'CAMERA':
            bpy.data.objects.remove(o, do_unlink=True)
    cam_data = bpy.data.cameras.new(name="CameraData")
    cam_data.lens = lens
    cam_data.clip_end = 1000
    cam_obj = bpy.data.objects.new("Camera", cam_data)
    cam_obj.location = loc
    cam_obj.rotation_euler = (math.radians(rot_x_deg), 0, 0)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    print("Camera created at " + str(loc))
    return cam_obj


def make_light(energy=5000, loc=(0, 0, 0), color=(1, 0.95, 0.8),
               ltype='POINT', rot_euler=None):
    light_data = bpy.data.lights.new(name="Light", type=ltype)
    light_data.energy = energy
    light_data.color = color
    light_obj = bpy.data.objects.new("Light", light_data)
    light_obj.location = loc
    if rot_euler:
        light_obj.rotation_euler = rot_euler
    bpy.context.scene.collection.objects.link(light_obj)
    return light_obj


# ------------------------------------------------------------------ BUILD

def build_mercury():
    reset()
    set_black_world()
    p = sphere("Mercury", 1.0)
    p.data.materials.append(mat_diffuse("Mercury_Mat", "mercury.jpg", 0.95))
    add_spin(p, 0.03, FRAMES)
    l = make_light(energy=4, loc=(8, -5, 5), color=(1, 0.95, 0.85), ltype='SUN')
    l.rotation_euler = (math.radians(45), 0, math.radians(45))
    make_camera((0, -8, 0), 90, lens=50)
    print("Mercury ready")


build_mercury()