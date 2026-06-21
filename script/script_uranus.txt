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
    L.new(tc.outputs["UV"],  tx.inputs["Vector"])
    if i: L.new(tx.outputs["Color"], pr.inputs["Base Color"])
    L.new(pr.outputs["BSDF"], ou.inputs["Surface"])
    return m


def mat_uranus_rings(name):
    m = bpy.data.materials.new(name)
    m.use_nodes    = True
    m.blend_method = 'BLEND'
    N = m.node_tree.nodes
    L = m.node_tree.links
    N.clear()
    pr = N.new("ShaderNodeBsdfPrincipled")
    pr.inputs["Base Color"].default_value = (0.08, 0.08, 0.09, 1)
    pr.inputs["Roughness"].default_value  = 0.95
    pr.inputs["Alpha"].default_value      = 0.6
    ou = N.new("ShaderNodeOutputMaterial")
    L.new(pr.outputs["BSDF"], ou.inputs["Surface"])
    return m


# ----------------------------------------------------------- SEAMLESS RING MESH

def make_ring_mesh(name, inner, outer, steps=512):
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

def build_uranus():
    reset()
    set_black_world()

    # Planet — 97.8° tilt, retrograde spin
    p = sphere("Uranus", 1.4)
    p.data.materials.append(
        mat_diffuse("Uranus_Mat", "uranus.jpg", 0.3, (0.4, 0.8, 0.85, 1)))
    add_spin(p, 97.8, FRAMES, retrograde=True)

    # Seamless ring mesh
    ring = make_ring_mesh("Uranus_Rings", inner=1.7, outer=2.4, steps=512)
    ring.data.materials.append(mat_uranus_rings("Uranus_RingMat"))

    # Spin on Z exactly like Saturn — tilt locked, full 360 over 250 frames
    TILT = math.radians(90)
    ring.rotation_mode  = 'XYZ'
    ring.rotation_euler = (TILT, 0, 0)

    # Lighting
    make_sun_light(
        energy=10.0,
        rot_euler=(math.radians(45), 0, math.radians(45)),
        color=(1, 0.95, 0.85))

    # Camera straight on so ring spin is clearly visible
    make_camera(loc=(15, 4, 4), rot_x_deg=75, lens=75, rot_z_deg=105)
    print("Uranus ready")


build_uranus()