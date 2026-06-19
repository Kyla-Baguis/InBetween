"""
EARTH - Blender 5.1.1 compatible
Texture from C:\\Users\\ClearBug\\Downloads\\textures

Expected texture files:
    earth_day.jpg
    earth_night.jpg    (optional – city lights on dark side)
    earth_clouds.jpg   (optional – cloud shell)

HOW TO USE:
    1. Open this file in Blender Text Editor (Scripting tab)
    2. Press Run Script or Alt+P
    3. Press NUMPAD 0 to view through camera, SPACE to play
"""

import bpy
import math
from bpy_extras import anim_utils

TEXTURES = r"C:\Users\ClearBug\Downloads\textures"
FPS      = 24
FRAMES   = 250


# ------------------------------------------------------------------ UTILITIES

def reset():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for b in bpy.data.meshes:    bpy.data.meshes.remove(b)
    for b in bpy.data.materials: bpy.data.materials.remove(b)
    for b in bpy.data.images:    bpy.data.images.remove(b)
    s = bpy.context.scene
    s.frame_start         = 1
    s.frame_end           = FRAMES
    s.render.fps          = FPS
    s.render.resolution_x = 1920
    s.render.resolution_y = 1080


def tex(filename):
    try:
        return bpy.data.images.load(TEXTURES + "\\" + filename)
    except Exception:
        print("WARNING: Texture not found: " + filename)
        return None


def sphere(name, r, loc=(0, 0, 0), segs=64):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segs, ring_count=segs // 2, radius=r, location=loc)
    o = bpy.context.active_object
    o.name = name
    bpy.ops.object.shade_smooth()
    return o


def atmo_sphere(name, r, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=64, ring_count=32, radius=r, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.rotation_euler[2] = math.radians(90)
    bpy.ops.object.shade_smooth()
    return o


def set_linear_fcurves(obj):
    action      = obj.animation_data.action
    action_slot = obj.animation_data.action_slot
    channelbag  = anim_utils.action_get_channelbag_for_slot(action, action_slot)
    if channelbag:
        for fc in channelbag.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


def add_spin(obj, tilt_deg, frames=FRAMES, retrograde=False):
    d  = -1 if retrograde else 1
    tx = math.radians(tilt_deg)
    obj.rotation_mode = 'XYZ'
    obj.rotation_euler = (tx, 0, 0)
    obj.keyframe_insert(data_path="rotation_euler", frame=1)
    obj.rotation_euler = (tx, 0, d * math.radians(360))
    obj.keyframe_insert(data_path="rotation_euler", frame=frames)
    set_linear_fcurves(obj)


def set_gray_world():
    w  = bpy.data.worlds["World"]
    w.use_nodes = True
    N  = w.node_tree.nodes
    bg = N.get("Background") or N.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value    = (0, 0, 0, 1)
    bg.inputs["Strength"].default_value = 0


def make_camera(loc, rot_x_deg, lens=50, rot_z_deg=0):
    for o in list(bpy.data.objects):
        if o.type == 'CAMERA':
            bpy.data.objects.remove(o, do_unlink=True)
    cam_data           = bpy.data.cameras.new(name="CameraData")
    cam_data.lens      = lens
    cam_data.clip_end  = 1000
    cam_obj            = bpy.data.objects.new("Camera", cam_data)
    cam_obj.location   = loc
    cam_obj.rotation_euler = (
        math.radians(rot_x_deg), 0, math.radians(rot_z_deg))
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    return cam_obj


def make_sun_light(energy, rot_euler, color=(1, 0.98, 0.9)):
    ld        = bpy.data.lights.new(name="SunLight", type='SUN')
    ld.energy = energy
    ld.color  = color
    lo        = bpy.data.objects.new("SunLight", ld)
    lo.rotation_euler = rot_euler
    bpy.context.scene.collection.objects.link(lo)
    return lo


# ------------------------------------------------------------------ MATERIALS

def mat_diffuse_simple(name, roughness=0.9, col=(0.5, 0.5, 0.5, 1)):
    """Plain Principled material with no texture — used for the Moon."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    pr = m.node_tree.nodes.get("Principled BSDF")
    pr.inputs["Base Color"].default_value = col
    pr.inputs["Roughness"].default_value  = roughness
    return m


def mat_earth(name):
    """Day texture + subtle night-light emission blend."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    N = m.node_tree.nodes
    L = m.node_tree.links
    N.clear()

    tc    = N.new("ShaderNodeTexCoord")
    mp    = N.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value[2] = math.radians(90)

    day   = N.new("ShaderNodeTexImage")
    day.label = "Day"
    i = tex("earth.jpg")
    if i: day.image = i

    night = N.new("ShaderNodeTexImage")
    night.label = "Night"
    n = tex("earth_night.jpg")
    if n: night.image = n

    pr    = N.new("ShaderNodeBsdfPrincipled")
    pr.inputs["Roughness"].default_value = 0.4
    if i: L.new(day.outputs["Color"], pr.inputs["Base Color"])

    em    = N.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 0.6
    if n: L.new(night.outputs["Color"], em.inputs["Color"])

    ou    = N.new("ShaderNodeOutputMaterial")
    L.new(tc.outputs["UV"],       mp.inputs["Vector"])
    L.new(mp.outputs["Vector"],   day.inputs["Vector"])
    L.new(mp.outputs["Vector"],   night.inputs["Vector"])
    L.new(pr.outputs["BSDF"],     ou.inputs["Surface"])
    return m


def mat_cloud(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.blend_method = 'BLEND'
    N = m.node_tree.nodes
    L = m.node_tree.links
    N.clear()
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value[2] = math.radians(90)
    tx = N.new("ShaderNodeTexImage")
    i  = tex("earth_clouds.jpg")
    if i: tx.image = i
    pr = N.new("ShaderNodeBsdfPrincipled")
    pr.inputs["Base Color"].default_value = (1, 1, 1, 1)
    pr.inputs["Roughness"].default_value  = 0.5
    pr.inputs["Alpha"].default_value      = 0.25
    ou = N.new("ShaderNodeOutputMaterial")
    L.new(tc.outputs["UV"],    mp.inputs["Vector"])
    L.new(mp.outputs["Vector"], tx.inputs["Vector"])
    if i: L.new(tx.outputs["Color"], pr.inputs["Base Color"])
    L.new(pr.outputs["BSDF"], ou.inputs["Surface"])
    return m


def mat_atmo(name, color, strength=2.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.blend_method = 'BLEND'
    N = m.node_tree.nodes
    L = m.node_tree.links
    N.clear()
    lw = N.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.15
    # Power node sharpens the falloff so only a thin sliver glows
    pw = N.new("ShaderNodeMath")
    pw.operation = 'POWER'
    pw.inputs[1].default_value = 30.0
    em = N.new("ShaderNodeEmission")
    em.inputs["Color"].default_value    = color
    em.inputs["Strength"].default_value = strength
    tr = N.new("ShaderNodeBsdfTransparent")
    mx = N.new("ShaderNodeMixShader")
    ou = N.new("ShaderNodeOutputMaterial")
    L.new(lw.outputs["Fresnel"],  pw.inputs[0])
    L.new(pw.outputs["Value"],    mx.inputs["Fac"])
    L.new(tr.outputs["BSDF"],     mx.inputs[1])
    L.new(em.outputs["Emission"], mx.inputs[2])
    L.new(mx.outputs["Shader"],   ou.inputs["Surface"])
    return m


# ------------------------------------------------------------------ BUILD

def build_earth():
    reset()
    set_gray_world()

    # Main body
    p = sphere("Earth", 0.9)
    p.data.materials.append(mat_earth("Earth_Mat"))
    add_spin(p, 23.4, FRAMES)

    # Atmosphere glow — subtle rim only
    a = atmo_sphere("Earth_Atmo", 0.97)
    a.data.materials.append(
        mat_atmo("Earth_AtmoMat", (0.25, 0.55, 1.0, 1), strength=0.8))

    # Moon — orbits Earth once over the animation, smaller and farther so it doesn't dominate frame
    moon = sphere("Moon", 0.18, loc=(3.5, 0, 0))
    moon.visible_shadow = False
    moon.data.materials.append(
        mat_diffuse_simple("Moon_Mat", roughness=0.9, col=(0.55, 0.53, 0.5, 1)))

    moon_orbit = bpy.data.objects.new("Moon_Orbit", None)
    bpy.context.scene.collection.objects.link(moon_orbit)
    moon.parent = moon_orbit
    moon_orbit.rotation_mode = 'XYZ'
    # Tilt the orbit plane so the moon doesn't pass straight through the camera's view
    moon_orbit.rotation_euler = (math.radians(15), 0, 0)
    moon_orbit.keyframe_insert(data_path="rotation_euler", frame=1)
    moon_orbit.rotation_euler = (math.radians(15), 0, math.radians(360))
    moon_orbit.keyframe_insert(data_path="rotation_euler", frame=FRAMES)
    set_linear_fcurves(moon_orbit)

    # Moon spins slowly on its own axis too (tidally locked look is optional)
    add_spin(moon, 0, FRAMES)

    # Sun light angled more toward the camera so the lit side is bigger in frame
    make_sun_light(
        energy=10.0,
        rot_euler=(math.radians(60), 0, math.radians(50)),
        color=(1, 0.98, 0.92))

    # Centered camera, pulled back a bit to fit the moon's orbit
    make_camera(loc=(-8, 0, 0), rot_x_deg=90, lens=60, rot_z_deg=-90)
    print("Earth ready")


build_earth()