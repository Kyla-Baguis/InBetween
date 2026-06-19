"""
SATURN - Blender 5.1.1 compatible
Texture from C:\\Users\\ClearBug\\Downloads\\textures

Expected texture files:
    saturn.jpg
    saturn_rings.png   (RGBA – alpha channel = ring transparency)

HOW TO USE:
    1. Open this file in Blender Text Editor (Scripting tab)
    2. Press Run Script or Alt+P
    3. Press NUMPAD 0 to view through camera, SPACE to play
"""

import bpy
import math
import bmesh
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


def set_black_world():
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

def mat_diffuse(name, img_file, roughness=0.8, col=(0.5, 0.5, 0.5, 1)):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    N = m.node_tree.nodes
    L = m.node_tree.links
    N.clear()
    tc = N.new("ShaderNodeTexCoord")
    tx = N.new("ShaderNodeTexImage")
    i  = tex(img_file)
    if i: tx.image = i
    pr = N.new("ShaderNodeBsdfPrincipled")
    pr.inputs["Base Color"].default_value = col
    pr.inputs["Roughness"].default_value  = roughness
    ou = N.new("ShaderNodeOutputMaterial")
    L.new(tc.outputs["UV"],   tx.inputs["Vector"])
    if i: L.new(tx.outputs["Color"], pr.inputs["Base Color"])
    L.new(pr.outputs["BSDF"], ou.inputs["Surface"])
    return m


def mat_atmo(name, color, strength=0.35):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.blend_method = 'BLEND'
    N = m.node_tree.nodes
    L = m.node_tree.links
    N.clear()
    lw = N.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.4
    em = N.new("ShaderNodeEmission")
    em.inputs["Color"].default_value    = color
    em.inputs["Strength"].default_value = strength
    tr = N.new("ShaderNodeBsdfTransparent")
    mx = N.new("ShaderNodeMixShader")
    ou = N.new("ShaderNodeOutputMaterial")
    L.new(lw.outputs["Facing"],   mx.inputs["Fac"])
    L.new(tr.outputs["BSDF"],     mx.inputs[1])
    L.new(em.outputs["Emission"], mx.inputs[2])
    L.new(mx.outputs["Shader"],   ou.inputs["Surface"])
    return m


def mat_ring(name, img_file):
    m = bpy.data.materials.new(name)
    m.use_nodes    = True
    m.blend_method = 'BLEND'
    N = m.node_tree.nodes
    L = m.node_tree.links
    N.clear()

    tc   = N.new("ShaderNodeTexCoord")
    sep  = N.new("ShaderNodeSeparateXYZ")

    com2 = N.new("ShaderNodeCombineXYZ")
    com2.inputs[2].default_value = 0.0

    len2 = N.new("ShaderNodeVectorMath")
    len2.operation = 'LENGTH'

    sub  = N.new("ShaderNodeMath")
    sub.operation = 'SUBTRACT'
    sub.inputs[1].default_value = 2.4

    div  = N.new("ShaderNodeMath")
    div.operation = 'DIVIDE'
    div.inputs[1].default_value = 2.2

    com  = N.new("ShaderNodeCombineXYZ")
    com.inputs[1].default_value = 0.5
    com.inputs[2].default_value = 0.0

    tx   = N.new("ShaderNodeTexImage")
    i    = tex(img_file)
    if i:
        tx.image = i
        tx.image.alpha_mode = 'STRAIGHT'
        tx.extension = 'CLIP'          # FIX: prevents texture wrapping at edges

    pr   = N.new("ShaderNodeBsdfPrincipled")
    pr.inputs["Base Color"].default_value = (0.6, 0.5, 0.35, 1)
    pr.inputs["Roughness"].default_value  = 0.7
    if i:
        L.new(tx.outputs["Color"], pr.inputs["Base Color"])
        L.new(tx.outputs["Alpha"], pr.inputs["Alpha"])

    ou   = N.new("ShaderNodeOutputMaterial")

    L.new(tc.outputs["Object"],   sep.inputs["Vector"])
    L.new(sep.outputs["X"],       com2.inputs[0])
    L.new(sep.outputs["Y"],       com2.inputs[1])
    L.new(com2.outputs["Vector"], len2.inputs[0])
    L.new(len2.outputs["Value"],  sub.inputs[0])
    L.new(sub.outputs["Value"],   div.inputs[0])
    L.new(div.outputs["Value"],   com.inputs[0])
    L.new(com.outputs["Vector"],  tx.inputs["Vector"])
    L.new(pr.outputs["BSDF"],     ou.inputs["Surface"])
    return m


# ----------------------------------------------------------- SEAMLESS RING MESH

def make_ring_mesh(name, inner=2.4, outer=4.6, steps=512):
    """Flat annulus built from quads — no torus topology, no spoke lines."""
    me = bpy.data.meshes.new(name + "Mesh")
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)

    bm       = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    for i in range(steps):
        a0 = (i       / steps) * math.tau
        a1 = ((i + 1) / steps) * math.tau

        vi  = bm.verts.new((inner * math.cos(a0), inner * math.sin(a0), 0))
        vo  = bm.verts.new((outer * math.cos(a0), outer * math.sin(a0), 0))
        vo2 = bm.verts.new((outer * math.cos(a1), outer * math.sin(a1), 0))
        vi2 = bm.verts.new((inner * math.cos(a1), inner * math.sin(a1), 0))

        f = bm.faces.new([vi, vo, vo2, vi2])
        f.loops[0][uv_layer].uv = (0.0, 0.5)
        f.loops[1][uv_layer].uv = (1.0, 0.5)
        f.loops[2][uv_layer].uv = (1.0, 0.5)
        f.loops[3][uv_layer].uv = (0.0, 0.5)

    bm.to_mesh(me)
    bm.free()
    me.update()
    return ob


# ------------------------------------------------------------------ BUILD

def build_saturn():
    reset()
    set_black_world()

    # Planet body
    p = sphere("Saturn", 2.0)
    p.data.materials.append(
        mat_diffuse("Saturn_Mat", "saturn.jpg", 0.5, (0.85, 0.75, 0.55, 1)))
    add_spin(p, 26.7, FRAMES)

    # FIX 1: Replace torus with seamless flat ring mesh (removes spoke lines)
    ring = make_ring_mesh("Saturn_Rings", inner=2.4, outer=4.6, steps=512)
    ring.data.materials.append(
        mat_ring("Saturn_RingMat", "saturn_ring.png"))

    # FIX 2: Match ring tilt to planet (26.7°) and animate spin
    TILT = math.radians(2)
    ring.rotation_mode  = 'XYZ'
    ring.rotation_euler = (TILT, 0, 0)
    ring.keyframe_insert(data_path="rotation_euler", frame=1)
    ring.rotation_euler = (TILT, 0, math.radians(360))
    ring.keyframe_insert(data_path="rotation_euler", frame=FRAMES)
    set_linear_fcurves(ring)

    # Lighting
    make_sun_light(
        energy=8.0,
        rot_euler=(math.radians(30), 0, math.radians(-20)),
        color=(1, 0.92, 0.8))

    # Camera
    make_camera(loc=(0, -23, 10), rot_x_deg=65, lens=70, rot_z_deg=0)
    print("Saturn ready")


build_saturn()