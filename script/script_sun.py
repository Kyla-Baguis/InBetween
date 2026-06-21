import bpy
import os
import math
from bpy_extras import anim_utils

TEXTURE_PATH = r"C:\Users\ClearBug\Downloads\textures\sun.jpg"

AXIAL_TILT_DEGREES = 7.25
TOTAL_FRAMES = 250
FPS          = 24

# ------------------------------------------------------------------ RESET

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

for block in bpy.data.meshes:    bpy.data.meshes.remove(block)
for block in bpy.data.materials: bpy.data.materials.remove(block)
for block in bpy.data.images:    bpy.data.images.remove(block)
for block in bpy.data.lights:    bpy.data.lights.remove(block)

# ------------------------------------------------------------------ SUN SPHERE

bpy.ops.mesh.primitive_uv_sphere_add(
    segments=128,
    ring_count=64,
    radius=2.0,
    location=(0, 0, 0)
)
sun_obj = bpy.context.active_object
sun_obj.name = "Sun"
bpy.ops.object.shade_smooth()

# ------------------------------------------------------------------ MATERIAL

mat = bpy.data.materials.new(name="Sun_Material")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

output   = nodes.new("ShaderNodeOutputMaterial")
output.location = (800, 0)

emission = nodes.new("ShaderNodeEmission")
emission.location = (550, 0)
emission.inputs["Strength"].default_value = 5.0

tex_coord = nodes.new("ShaderNodeTexCoord")
tex_coord.location = (-600, 0)

mapping = nodes.new("ShaderNodeMapping")
mapping.location = (-400, 0)
mapping.inputs["Scale"].default_value = (1.0, 1.0, 1.0)
links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])

img_node = nodes.new("ShaderNodeTexImage")
img_node.location = (-150, 0)

abs_path = bpy.path.abspath(TEXTURE_PATH)
if os.path.exists(abs_path):
    img = bpy.data.images.load(abs_path)
    img_node.image = img
    print(f"[Sun] Texture loaded: {abs_path}")
else:
    print(f"[Sun] WARNING - texture not found at: {abs_path}")

links.new(mapping.outputs["Vector"], img_node.inputs["Vector"])
links.new(img_node.outputs["Color"], emission.inputs["Color"])
links.new(emission.outputs["Emission"], output.inputs["Surface"])

sun_obj.data.materials.append(mat)

# ------------------------------------------------------------------ LIGHTS

bpy.ops.object.light_add(type='POINT', location=(0, 0, 0))
core_light = bpy.context.active_object
core_light.name = "Sun_Core_Light"
core_light.data.energy           = 5000.0
core_light.data.color            = (1.0, 0.9, 0.6)
core_light.data.shadow_soft_size = 2.0

# ------------------------------------------------------------------ WORLD

world = bpy.data.worlds["World"]
world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links
wn.clear()

out_w = wn.new("ShaderNodeOutputWorld")
bg_w  = wn.new("ShaderNodeBackground")
bg_w.inputs["Color"].default_value    = (0, 0, 0, 1)
bg_w.inputs["Strength"].default_value = 0
wl.new(bg_w.outputs["Background"], out_w.inputs["Surface"])

# ------------------------------------------------------------------ CAMERA

bpy.ops.object.camera_add(location=(0, -12, 0))
cam = bpy.context.active_object
cam.name = "Camera"
cam.rotation_euler = (1.5708, 0.0, 0.0)
cam.data.lens      = 50
bpy.context.scene.camera = cam

# ------------------------------------------------------------------ RENDER SETTINGS

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'

scene.render.resolution_x          = 1920
scene.render.resolution_y          = 1080
scene.render.resolution_percentage = 100

scene.view_settings.view_transform = 'Standard'
try:
    scene.view_settings.look = 'None'
except:
    scene.view_settings.look = ''

scene.view_settings.exposure = 0.0
scene.view_settings.gamma    = 1.0

scene.frame_start = 1
scene.frame_end   = TOTAL_FRAMES
scene.render.fps  = FPS

# ------------------------------------------------------------------ ANIMATION

bpy.context.view_layer.objects.active = sun_obj
sun_obj.select_set(True)

axial_tilt_radians = math.radians(AXIAL_TILT_DEGREES)

for frame_num in range(scene.frame_start, scene.frame_end + 1):
    scene.frame_set(frame_num)
    progress = (frame_num - 1) / TOTAL_FRAMES
    sun_obj.rotation_euler = (axial_tilt_radians, 0, math.radians(progress * 360.0))
    sun_obj.keyframe_insert(data_path="rotation_euler", index=0)
    sun_obj.keyframe_insert(data_path="rotation_euler", index=2)

action      = sun_obj.animation_data.action
action_slot = sun_obj.animation_data.action_slot
channelbag  = anim_utils.action_get_channelbag_for_slot(action, action_slot)
if channelbag:
    for fc in channelbag.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

scene.frame_set(1)
print("Sun ready — Ctrl+F12 to render")