import bpy
import bmesh
import math
import random
import mathutils
from bpy_extras import anim_utils

# ============================================================
# CONFIG
# ============================================================

random.seed(42)

SOLAR_SYSTEM_FRAMES = 250   # total animation length
SCENE_SCALE = 1.0           # global scale multiplier

# ── FIXED: was r"C:\Users\ClearBug\Downloads\textrure"  (typo) ──────────────
TEXTURE_DIR = r"C:\Users\ClearBug\Downloads\textures"
# ────────────────────────────────────────────────────────────────────────────

# Texture files expected in that folder:
#   earth.jpg, sun.jpg, mars.jpg, mercury.jpg, venus.jpg, moon.jpg,
#   jupiter.jpg, saturn.jpg, saturn_ring.jpg (or saturn_ring.png with alpha),
#   uranus.jpg, neptune.jpg, stars.jpg, universe.jpg
# The loader tries .jpg / .jpeg / .png automatically, so bare names work too.


def clear_scene():
    bpy.ops.object.select_all(action='DESELECT')
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for block in list(bpy.data.meshes):
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in list(bpy.data.materials):
        if block.users == 0:
            bpy.data.materials.remove(block)
    for block in list(bpy.data.images):
        if block.users == 0:
            bpy.data.images.remove(block)
    for block in list(bpy.data.worlds):
        if block.users == 0:
            bpy.data.worlds.remove(block)

clear_scene()

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = SOLAR_SYSTEM_FRAMES
scene.render.engine = 'CYCLES'

# ============================================================
# HELPERS
# ============================================================

def new_material(name, base_color=(1, 1, 1, 1), emission_color=None, emission_strength=0.0,
                  roughness=0.6, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (300, 0)

    if emission_color is not None:
        emission = nodes.new('ShaderNodeEmission')
        emission.location = (0, 0)
        emission.inputs['Color'].default_value = emission_color
        emission.inputs['Strength'].default_value = emission_strength
        links.new(emission.outputs['Emission'], output.inputs['Surface'])
    else:
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.location = (0, 0)
        bsdf.inputs['Base Color'].default_value = base_color
        bsdf.inputs['Roughness'].default_value = roughness
        bsdf.inputs['Metallic'].default_value = metallic
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    return mat


def _build_texture_map():
    """
    Scans TEXTURE_DIR once at startup and returns a dict mapping
    lowercased stem (filename without extension) → full path.
    Also prints every file found so you can see exactly what's available.
    """
    import os
    result = {}
    if not os.path.isdir(TEXTURE_DIR):
        print(f"[TEXTURE ERROR] Folder not found: {TEXTURE_DIR}")
        return result
    print(f"[TEXTURE] Scanning folder: {TEXTURE_DIR}")
    for fname in os.listdir(TEXTURE_DIR):
        stem, ext = os.path.splitext(fname)
        if ext.lower() in (".jpg", ".jpeg", ".png", ".tga", ".exr", ".hdr"):
            key = stem.lower()
            full = os.path.join(TEXTURE_DIR, fname)
            result[key] = full
            print(f"  found: {fname}  →  key='{key}'")
    if not result:
        print("[TEXTURE WARNING] No image files found in that folder!")
    return result

# Built once when the script runs — all texture lookups use this map
_TEX_MAP = _build_texture_map()


def load_texture_image(keyword):
    """
    Finds an image whose filename (stem) best matches `keyword`.

    Matching strategy (most-to-least strict):
      1. Exact stem match  (e.g. keyword "earth"  → "earth.jpg")
      2. Stem starts with keyword  ("saturn_ring" → "saturn_ring.jpg")
      3. Stem contains keyword  ("2k_earth_daymap" → matches "earth")

    All comparisons are case-insensitive.
    Prints what it found (or didn't) so the console tells you exactly
    what happened for every planet.
    """
    kw = keyword.lower()
    # Strip extension if the caller passed one (e.g. "earth.jpg" → "earth")
    import os as _os
    kw_stem = _os.path.splitext(kw)[0]

    # Priority 1 – exact match
    if kw_stem in _TEX_MAP:
        path = _TEX_MAP[kw_stem]
        print(f"[TEXTURE] '{keyword}'  →  exact match: {_os.path.basename(path)}")
        return _load_path(path)

    # Priority 2 – stem starts with keyword
    for key, path in _TEX_MAP.items():
        if key.startswith(kw_stem):
            print(f"[TEXTURE] '{keyword}'  →  prefix match: {_os.path.basename(path)}")
            return _load_path(path)

    # Priority 3 – stem contains keyword
    for key, path in _TEX_MAP.items():
        if kw_stem in key:
            print(f"[TEXTURE] '{keyword}'  →  substring match: {_os.path.basename(path)}")
            return _load_path(path)

    print(f"[TEXTURE WARNING] No file matched keyword '{keyword}' — using flat colour fallback.")
    return None


def _load_path(full_path):
    """Load a single image file and return the datablock, or None on failure."""
    try:
        img = bpy.data.images.load(full_path, check_existing=True)
        img.reload()
        if not img.has_data:
            print(f"  ↳ WARNING: loaded but no pixel data in {full_path}")
            return None
        return img
    except RuntimeError as e:
        print(f"  ↳ ERROR loading {full_path}: {e}")
        return None


def new_textured_material(name, texture_filename, fallback_color=(0.6, 0.6, 0.6, 1),
                           emission=False, emission_strength=2.0, roughness=0.85, metallic=0.0):
    """
    Builds a material from an image texture file. Falls back to a flat-color
    material if the file can't be found so the script never crashes.
    """
    image = load_texture_image(texture_filename)

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (600, 0)

    if image is not None:
        tex_coord = nodes.new('ShaderNodeTexCoord')
        tex_coord.location = (-600, 0)

        mapping = nodes.new('ShaderNodeMapping')
        mapping.location = (-400, 0)
        links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

        tex_image = nodes.new('ShaderNodeTexImage')
        tex_image.location = (-150, 0)
        tex_image.image = image
        links.new(mapping.outputs['Vector'], tex_image.inputs['Vector'])

        if emission:
            emission_node = nodes.new('ShaderNodeEmission')
            emission_node.location = (250, 0)
            emission_node.inputs['Strength'].default_value = emission_strength
            links.new(tex_image.outputs['Color'], emission_node.inputs['Color'])
            links.new(emission_node.outputs['Emission'], output.inputs['Surface'])
        else:
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.location = (250, 0)
            bsdf.inputs['Roughness'].default_value = roughness
            bsdf.inputs['Metallic'].default_value = metallic
            links.new(tex_image.outputs['Color'], bsdf.inputs['Base Color'])
            links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    else:
        if emission:
            emission_node = nodes.new('ShaderNodeEmission')
            emission_node.location = (0, 0)
            emission_node.inputs['Color'].default_value = fallback_color
            emission_node.inputs['Strength'].default_value = emission_strength
            links.new(emission_node.outputs['Emission'], output.inputs['Surface'])
        else:
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.location = (0, 0)
            bsdf.inputs['Base Color'].default_value = fallback_color
            bsdf.inputs['Roughness'].default_value = roughness
            bsdf.inputs['Metallic'].default_value = metallic
            links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    return mat


def get_fcurves(obj):
    """
    Version-safe fcurve getter for Blender 4.4+/5.x layered Action API,
    with legacy fallback.
    """
    if obj.animation_data is None:
        return []
    action = obj.animation_data.action
    if action is None:
        return []

    if hasattr(action, "fcurves"):
        return action.fcurves

    try:
        slot = obj.animation_data.action_slot
        channelbag = anim_utils.action_get_channelbag_for_slot(action, slot)
        if channelbag:
            return channelbag.fcurves
    except (AttributeError, TypeError):
        pass

    return []


def set_linear_fcurves(obj):
    """Set every fcurve keyframe on obj to LINEAR interpolation (version-safe)."""
    for fcurve in get_fcurves(obj):
        for kp in fcurve.keyframe_points:
            kp.interpolation = 'LINEAR'


def create_empty(name, location=(0, 0, 0)):
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_size = 0.15
    empty.empty_display_type = 'PLAIN_AXES'
    empty.location = location
    scene.collection.objects.link(empty)
    return empty


def add_sphere(name, radius, segments=64, rings=32):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=segments,
                                          ring_count=rings, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    bpy.ops.object.shade_smooth()
    return obj


def add_orbit_animation(obj, orbit_radius, orbit_period_frames, start_angle_deg=0.0,
                         tilt_deg=0.0, clockwise=False):
    controller = create_empty(f"{obj.name}_OrbitController", location=(0, 0, 0))
    controller.rotation_euler[0] = math.radians(tilt_deg)

    obj.parent = controller
    obj.location = (orbit_radius, 0, 0)

    direction = -1 if clockwise else 1
    start_rad = math.radians(start_angle_deg)

    total_frames = SOLAR_SYSTEM_FRAMES
    steps = max(2, int(total_frames / max(1, orbit_period_frames) * 8))
    steps = min(steps, 64)

    controller.rotation_mode = 'XYZ'
    for i in range(steps + 1):
        frame = 1 + (total_frames - 1) * (i / steps)
        angle = start_rad + direction * 2 * math.pi * (frame / orbit_period_frames)
        controller.rotation_euler = (math.radians(tilt_deg), 0, angle)
        controller.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)

    set_linear_fcurves(controller)

    return controller


def add_self_rotation(obj, period_frames, axis_index=2, clockwise=False):
    direction = -1 if clockwise else 1
    total_frames = SOLAR_SYSTEM_FRAMES
    obj.rotation_mode = 'XYZ'

    start_val = obj.rotation_euler[axis_index]
    obj.rotation_euler[axis_index] = start_val
    obj.keyframe_insert(data_path="rotation_euler", index=axis_index, frame=1)

    end_val = start_val + direction * 2 * math.pi * (total_frames / period_frames)
    obj.rotation_euler[axis_index] = end_val
    obj.keyframe_insert(data_path="rotation_euler", index=axis_index, frame=total_frames)

    if obj.animation_data and obj.animation_data.action:
        for fcurve in get_fcurves(obj):
            if fcurve.array_index == axis_index:
                for kp in fcurve.keyframe_points:
                    kp.interpolation = 'LINEAR'
                fcurve.extrapolation = 'LINEAR'


def make_planet(name, radius, distance, color, orbit_period, spin_period,
                tilt_deg=0.0, emission=False, emission_strength=5.0, segments=64, rings=32,
                texture=None):
    obj = add_sphere(name, radius, segments=segments, rings=rings)

    if texture:
        mat = new_textured_material(f"{name}_Mat", texture, fallback_color=color,
                                     emission=emission, emission_strength=emission_strength,
                                     roughness=0.85)
    elif emission:
        mat = new_material(f"{name}_Mat", emission_color=color, emission_strength=emission_strength)
    else:
        mat = new_material(f"{name}_Mat", base_color=color, roughness=0.75)
    obj.data.materials.append(mat)

    obj.rotation_euler[0] = math.radians(tilt_deg)

    add_self_rotation(obj, spin_period, axis_index=2)

    if distance > 0:
        add_orbit_animation(obj, distance, orbit_period, start_angle_deg=random.uniform(0, 360))

    return obj


# ============================================================
# SATURN RING MESH + MATERIAL  (ported from script_saturn.txt)
# ------------------------------------------------------------
# Replaces the old generic make_ring() bmesh-disk approach for Saturn
# specifically: this builds a true seamless flat annulus (radial quads,
# no shared seam edge) and a material whose UVs are derived procedurally
# from object-space radius/angle, so the ring texture maps correctly
# without needing per-vertex UV unwrap fixes.
# ============================================================

def make_ring_mesh(name, inner, outer, steps=512):
    """Flat annulus built from quads — no torus topology, no spoke lines."""
    me = bpy.data.meshes.new(name + "Mesh")
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)

    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    for i in range(steps):
        a0 = (i / steps) * math.tau
        a1 = ((i + 1) / steps) * math.tau

        vi = bm.verts.new((inner * math.cos(a0), inner * math.sin(a0), 0))
        vo = bm.verts.new((outer * math.cos(a0), outer * math.sin(a0), 0))
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


def mat_saturn_ring(name, texture_filename, inner, outer):
    """
    Procedural ring material: maps object-space radius -> texture U
    coordinate, so the band of ring texture is read out correctly from
    inner edge to outer edge regardless of mesh UVs. Ported directly
    from script_saturn.txt's mat_ring().
    """
    image = load_texture_image(texture_filename)

    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.blend_method = 'BLEND'
    N = m.node_tree.nodes
    L = m.node_tree.links
    N.clear()

    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")

    com2 = N.new("ShaderNodeCombineXYZ")
    com2.inputs[2].default_value = 0.0

    len2 = N.new("ShaderNodeVectorMath")
    len2.operation = 'LENGTH'

    sub = N.new("ShaderNodeMath")
    sub.operation = 'SUBTRACT'
    sub.inputs[1].default_value = inner

    div = N.new("ShaderNodeMath")
    div.operation = 'DIVIDE'
    div.inputs[1].default_value = max(1e-6, outer - inner)

    com = N.new("ShaderNodeCombineXYZ")
    com.inputs[1].default_value = 0.5
    com.inputs[2].default_value = 0.0

    tx = N.new("ShaderNodeTexImage")
    if image is not None:
        tx.image = image
        tx.image.alpha_mode = 'STRAIGHT'
        tx.extension = 'CLIP'   # prevents texture wrapping/smearing at edges

    pr = N.new("ShaderNodeBsdfPrincipled")
    pr.inputs["Base Color"].default_value = (0.6, 0.5, 0.35, 1)
    pr.inputs["Roughness"].default_value = 0.7
    if image is not None:
        L.new(tx.outputs["Color"], pr.inputs["Base Color"])
        L.new(tx.outputs["Alpha"], pr.inputs["Alpha"])

    ou = N.new("ShaderNodeOutputMaterial")

    L.new(tc.outputs["Object"], sep.inputs["Vector"])
    L.new(sep.outputs["X"], com2.inputs[0])
    L.new(sep.outputs["Y"], com2.inputs[1])
    L.new(com2.outputs["Vector"], len2.inputs[0])
    L.new(len2.outputs["Value"], sub.inputs[0])
    L.new(sub.outputs["Value"], div.inputs[0])
    L.new(div.outputs["Value"], com.inputs[0])
    L.new(com.outputs["Vector"], tx.inputs["Vector"])
    L.new(pr.outputs["BSDF"], ou.inputs["Surface"])
    return m


def make_saturn_rings(planet_obj, planet_orbit_controller, planet_tilt_deg,
                       inner, outer, texture_filename, orbit_period_frames):
    """
    Builds Saturn's rings as a seamless annulus, tilts them to match the
    planet's axial tilt, parents them to the SAME orbit controller as the
    planet (so they travel together around the Sun), and gives the ring
    its own slow spin animation synced over the full timeline.
    """
    ring = make_ring_mesh(f"{planet_obj.name}_Rings", inner=inner, outer=outer, steps=512)
    ring.data.materials.append(
        mat_saturn_ring(f"{planet_obj.name}_RingMat", texture_filename, inner, outer))

    # Parent to the planet's orbit controller (not the planet itself) so the
    # ring orbits the Sun in lockstep with Saturn but spins independently.
    # IMPORTANT: must match the planet's own local offset (orbit_radius along
    # local X), otherwise the ring sits at the controller's origin — which is
    # world (0,0,0), i.e. inside the Sun — instead of out at Saturn's orbit.
    ring.parent = planet_orbit_controller
    ring.matrix_parent_inverse = planet_orbit_controller.matrix_world.inverted()
    ring.location = planet_obj.location.copy()

    tilt_rad = math.radians(planet_tilt_deg)
    ring.rotation_mode = 'XYZ'
    ring.rotation_euler = (tilt_rad, 0, 0)
    ring.keyframe_insert(data_path="rotation_euler", frame=1)
    ring.rotation_euler = (tilt_rad, 0, math.radians(360))
    ring.keyframe_insert(data_path="rotation_euler", frame=SOLAR_SYSTEM_FRAMES)
    set_linear_fcurves(ring)

    return ring


def make_ring(name, planet_obj, inner_radius, outer_radius, color, alpha=0.6, texture=None,
              segments=128):
    """Generic ring builder, still used for any non-Saturn ringed body if needed."""
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm = bmesh.new()

    outer_verts = []
    inner_verts = []
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        ox, oy = outer_radius * math.cos(angle), outer_radius * math.sin(angle)
        ix, iy = inner_radius * math.cos(angle), inner_radius * math.sin(angle)
        outer_verts.append(bm.verts.new((ox, oy, 0)))
        inner_verts.append(bm.verts.new((ix, iy, 0)))

    bm.verts.ensure_lookup_table()

    for i in range(segments):
        i2 = (i + 1) % segments
        bm.faces.new((outer_verts[i], outer_verts[i2], inner_verts[i2], inner_verts[i]))

    bm.normal_update()

    uv_layer = bm.loops.layers.uv.new("UVMap")
    for face in bm.faces:
        for loop in face.loops:
            v = loop.vert
            angle = math.atan2(v.co.y, v.co.x)
            u = (angle + math.pi) / (2 * math.pi)
            dist = math.hypot(v.co.x, v.co.y)
            v_coord = (dist - inner_radius) / max(1e-6, (outer_radius - inner_radius))
            loop[uv_layer].uv = (u, v_coord)

    bm.to_mesh(mesh)
    bm.free()

    ring = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(ring)

    if texture:
        mat = new_textured_material(f"{name}_Mat", texture, fallback_color=(*color, alpha),
                                     roughness=0.8)
    else:
        mat = new_material(f"{name}_Mat", base_color=(*color, alpha), roughness=0.8)
    mat.blend_method = 'BLEND'
    mat.show_transparent_back = False
    ring.data.materials.append(mat)

    ring.parent = planet_obj.parent
    ring.location = planet_obj.location.copy()

    return ring


# ============================================================
# SUN
# ============================================================

sun = add_sphere("Sun", radius=4.0, segments=64, rings=32)

sun_mat = new_textured_material("Sun_Mat", "sun", fallback_color=(1.0, 0.7, 0.2, 1.0),
                                 emission=True, emission_strength=12.0)
sun.data.materials.append(sun_mat)
add_self_rotation(sun, spin_period := 600, axis_index=2)

sun_light = bpy.data.lights.new(name="Sun_Light", type='POINT')
sun_light.energy = 200000
sun_light.color = (1.0, 0.85, 0.6)
sun_light.shadow_soft_size = 2.0
sun_light_obj = bpy.data.objects.new("Sun_Light", sun_light)
sun_light_obj.location = (0, 0, 0)
scene.collection.objects.link(sun_light_obj)

fill_light = bpy.data.lights.new(name="Fill_Light", type='SUN')
fill_light.energy = 1.5
fill_light.color = (0.7, 0.75, 0.9)
fill_light_obj = bpy.data.objects.new("Fill_Light", fill_light)
fill_light_obj.location = (0, 0, 50)
fill_light_obj.rotation_euler = (math.radians(45), math.radians(20), 0)
scene.collection.objects.link(fill_light_obj)

# ============================================================
# PLANETS
# texture= filenames now explicitly include .jpg so the loader finds them
# immediately without needing to guess extensions
# ============================================================

mercury = make_planet("Mercury", 0.38, 7,  (0.55, 0.5,  0.48, 1), 60,  58,   0.03, texture="mercury")
venus   = make_planet("Venus",   0.7,  10, (0.85, 0.7,  0.4,  1), 90,  244, 177.4, texture="venus")
earth   = make_planet("Earth",   0.75, 14, (0.2,  0.45, 0.9,  1), 150, 24,   23.4, texture="earth")
mars    = make_planet("Mars",    0.5,  18, (0.75, 0.35, 0.2,  1), 200, 25,   25.2, texture="mars")
jupiter = make_planet("Jupiter", 2.5,  28, (0.8,  0.65, 0.45, 1), 320, 10,    3.1, texture="jupiter")

# --- SATURN (rebuilt per script_saturn.txt) -----------------------------
SATURN_TILT_DEG = 26.7
saturn = make_planet("Saturn", 2.1, 36, (0.9, 0.8, 0.6, 1), 420, 11,
                      SATURN_TILT_DEG, texture="saturn")

# saturn.parent is the OrbitController created inside make_planet/add_orbit_animation
saturn_orbit_controller = saturn.parent

saturn_rings = make_saturn_rings(
    planet_obj=saturn,
    planet_orbit_controller=saturn_orbit_controller,
    planet_tilt_deg=SATURN_TILT_DEG,
    inner=2.6,
    outer=4.6,
    texture_filename="saturn_ring",
    orbit_period_frames=420,
)
# -------------------------------------------------------------------------

uranus  = make_planet("Uranus",  1.4,  44, (0.55, 0.85, 0.9,  1), 520, 17,   97.8, texture="uranus")
neptune = make_planet("Neptune", 1.35, 50, (0.25, 0.4,  0.95, 1), 620, 16,   28.3, texture="neptune")

# ============================================================
# ASTEROID BELT (between Mars and Jupiter, ~20 to 25 units)
# ============================================================

def create_asteroid_belt(count=140, inner=20.0, outer=25.0, min_size=0.05, max_size=0.2):
    belt_collection = bpy.data.collections.new("Asteroid_Belt")
    scene.collection.children.link(belt_collection)

    asteroid_mat = new_material("Asteroid_Mat", base_color=(0.35, 0.32, 0.3, 1), roughness=0.95)
    trail_mat = new_material("Meteor_Trail_Mat", emission_color=(1.0, 0.6, 0.25, 1.0),
                              emission_strength=4.0)
    trail_mat.blend_method = 'BLEND'

    bpy.ops.mesh.primitive_ico_sphere_add(radius=1.0, subdivisions=1, location=(0, 0, 0))
    base = bpy.context.active_object
    base.name = "Asteroid_Base"

    bm = bmesh.new()
    bm.from_mesh(base.data)
    for v in bm.verts:
        offset = random.uniform(0.75, 1.2)
        v.co *= offset
    bm.to_mesh(base.data)
    bm.free()

    base.data.materials.append(asteroid_mat)

    for old_coll in base.users_collection:
        old_coll.objects.unlink(base)
    belt_collection.objects.link(base)

    bpy.ops.mesh.primitive_cone_add(radius1=0.5, radius2=0.0, depth=1.0, location=(0, 0, 0))
    trail_base = bpy.context.active_object
    trail_base.name = "Meteor_Trail_Base"
    trail_base.rotation_euler[1] = math.radians(90)
    trail_base.data.materials.append(trail_mat)
    for old_coll in trail_base.users_collection:
        old_coll.objects.unlink(trail_base)
    belt_collection.objects.link(trail_base)

    asteroids = [base]

    for i in range(count - 1):
        ast = base.copy()
        ast.data = base.data.copy()
        ast.name = f"Asteroid_{i+1:03d}"
        belt_collection.objects.link(ast)

        size = random.uniform(min_size, max_size)
        ast.scale = (size, size, size)

        radius = random.uniform(inner, outer)
        angle = random.uniform(0, 2 * math.pi)
        height = random.uniform(-0.8, 0.8)

        ast.location = (radius * math.cos(angle), radius * math.sin(angle), height)
        ast.rotation_euler = (random.uniform(0, math.pi), random.uniform(0, math.pi),
                               random.uniform(0, math.pi))

        orbit_period = random.uniform(25, 70)
        add_self_rotation(ast, random.uniform(8, 20), axis_index=random.choice([0, 1, 2]))
        add_orbit_animation(ast, radius, orbit_period,
                             start_angle_deg=math.degrees(angle),
                             tilt_deg=random.uniform(-3, 3))

        trail = trail_base.copy()
        trail.data = trail_base.data.copy()
        trail.name = f"Meteor_Trail_{i+1:03d}"
        belt_collection.objects.link(trail)
        trail_length = size * random.uniform(6, 10)
        trail.parent = ast
        trail.matrix_parent_inverse = mathutils.Matrix.Identity(4)
        trail.scale = (trail_length, 1.4, 1.4)
        trail.location = (-trail_length * 0.5, 0, 0)

        asteroids.append(ast)

    base.hide_render = True
    base.hide_viewport = True
    trail_base.hide_render = True
    trail_base.hide_viewport = True

    return asteroids

asteroid_belt = create_asteroid_belt(count=180, inner=20.0, outer=25.0)

# ============================================================
# ISS — orbiting Earth
# ============================================================

def create_iss(parent_planet, planet_radius):
    iss_collection = bpy.data.collections.new("ISS")
    scene.collection.children.link(iss_collection)

    iss_mat_body = new_material("ISS_Body_Mat", base_color=(0.8, 0.8, 0.82, 1),
                                 roughness=0.3, metallic=0.7)
    iss_mat_panel = new_material("ISS_Panel_Mat", base_color=(0.05, 0.05, 0.2, 1),
                                  roughness=0.2, metallic=0.4)

    bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=0.5, location=(0, 0, 0))
    body = bpy.context.active_object
    body.name = "ISS_Body"
    body.rotation_euler[1] = math.radians(90)
    body.data.materials.append(iss_mat_body)
    for c in body.users_collection:
        c.objects.unlink(body)
    iss_collection.objects.link(body)

    panel_meshes = []
    for side, x_off in (("L", -0.55), ("R", 0.55)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x_off, 0, 0))
        panel = bpy.context.active_object
        panel.name = f"ISS_Panel_{side}"
        panel.scale = (0.45, 0.02, 0.18)
        panel.data.materials.append(iss_mat_panel)
        panel.parent = body
        for c in panel.users_collection:
            c.objects.unlink(panel)
        iss_collection.objects.link(panel)
        panel_meshes.append(panel)

    iss_root = create_empty("ISS_Root", location=(0, 0, 0))
    for old_coll in list(iss_root.users_collection):
        old_coll.objects.unlink(iss_root)
    iss_collection.objects.link(iss_root)

    body.parent = iss_root
    iss_root.scale = (0.3, 0.3, 0.3)

    orbit_radius = planet_radius + 0.35
    orbit_controller = create_empty("ISS_OrbitController", location=(0, 0, 0))
    orbit_controller.parent = parent_planet
    orbit_controller.rotation_euler[0] = math.radians(51.6)

    iss_root.parent = orbit_controller
    iss_root.location = (orbit_radius, 0, 0)

    iss_orbit_period = 18
    total_frames = SOLAR_SYSTEM_FRAMES
    steps = min(64, total_frames)
    orbit_controller.rotation_mode = 'XYZ'
    for i in range(steps + 1):
        frame = 1 + (total_frames - 1) * (i / steps)
        angle = 2 * math.pi * (frame / iss_orbit_period)
        orbit_controller.rotation_euler = (math.radians(51.6), 0, angle)
        orbit_controller.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)

    set_linear_fcurves(orbit_controller)

    add_self_rotation(body, period_frames=140, axis_index=2)

    return iss_root

iss = create_iss(earth, planet_radius=0.75)

# ============================================================
# MOON — orbiting Earth
# ============================================================

def create_moon(parent_planet, planet_radius, orbit_period=45, moon_radius=0.2, distance=1.6):
    moon = add_sphere("Moon", moon_radius, segments=48, rings=24)

    moon_mat = new_textured_material("Moon_Mat", "moon", fallback_color=(0.6, 0.6, 0.6, 1),
                                      roughness=0.9)
    moon.data.materials.append(moon_mat)

    add_self_rotation(moon, period_frames=orbit_period, axis_index=2)

    moon_controller = create_empty("Moon_OrbitController", location=(0, 0, 0))
    moon_controller.parent = parent_planet
    moon_controller.rotation_euler[0] = math.radians(5.1)

    moon.parent = moon_controller
    moon.location = (planet_radius + distance, 0, 0)

    total_frames = SOLAR_SYSTEM_FRAMES
    steps = min(64, total_frames)
    moon_controller.rotation_mode = 'XYZ'
    for i in range(steps + 1):
        frame = 1 + (total_frames - 1) * (i / steps)
        angle = 2 * math.pi * (frame / orbit_period)
        moon_controller.rotation_euler = (math.radians(5.1), 0, angle)
        moon_controller.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)

    set_linear_fcurves(moon_controller)

    return moon

moon = create_moon(earth, planet_radius=0.75)

# ============================================================
# STARFIELD BACKGROUND
# ============================================================

def create_starfield(count=400, radius=200):
    star_collection = bpy.data.collections.new("Starfield")
    scene.collection.children.link(star_collection)

    star_mat = new_material("Star_Mat", emission_color=(1, 1, 1, 1), emission_strength=3.0)

    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.15, subdivisions=0, location=(0, 0, 0))
    base = bpy.context.active_object
    base.name = "Star_Base"
    base.data.materials.append(star_mat)
    for c in base.users_collection:
        c.objects.unlink(base)
    star_collection.objects.link(base)

    for i in range(count - 1):
        star = base.copy()
        star.data = base.data
        star.name = f"Star_{i+1:04d}"
        star_collection.objects.link(star)

        theta = random.uniform(0, 2 * math.pi)
        phi = math.acos(random.uniform(-1, 1))
        star.location = (
            radius * math.sin(phi) * math.cos(theta),
            radius * math.sin(phi) * math.sin(theta),
            radius * math.cos(phi),
        )
        scale = random.uniform(0.3, 1.0)
        star.scale = (scale, scale, scale)

    base.hide_render = True
    base.hide_viewport = True

create_starfield()

# ============================================================
# CAMERA
# ============================================================

bpy.ops.object.camera_add(location=(0, -60, 22))
camera = bpy.context.active_object
camera.name = "Main_Camera"
camera.rotation_euler = (math.radians(68), 0, 0)
camera.data.lens = 35
scene.camera = camera

# ============================================================
# WORLD BACKGROUND
# ============================================================

world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
world_nodes = world.node_tree.nodes
world_links = world.node_tree.links
world_nodes.clear()

world_output = world_nodes.new('ShaderNodeOutputWorld')
world_output.location = (300, 0)

universe_image = load_texture_image("universe")
bg = world_nodes.new('ShaderNodeBackground')
bg.location = (0, 0)

if universe_image is not None:
    env_tex = world_nodes.new('ShaderNodeTexEnvironment')
    env_tex.location = (-300, 0)
    env_tex.image = universe_image
    world_links.new(env_tex.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.2
else:
    bg.inputs['Color'].default_value = (0.0, 0.0, 0.01, 1.0)
    bg.inputs['Strength'].default_value = 0.05

world_links.new(bg.outputs['Background'], world_output.inputs['Surface'])

# ============================================================
# AUTO-FRAME VIEWPORT
# ============================================================

for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for region in area.regions:
            if region.type == 'WINDOW':
                with bpy.context.temp_override(area=area, region=region):
                    bpy.ops.object.select_all(action='SELECT')
                    bpy.ops.view3d.view_selected()
                    bpy.ops.object.select_all(action='DESELECT')
                break
        break

print("Solar system build complete: Sun, 8 planets, seamless Saturn rings, "
      "180-asteroid belt, ISS orbiting Earth, starfield, camera.")
print(f"Texture folder: {TEXTURE_DIR}")
print(f"Animation: frames 1-{SOLAR_SYSTEM_FRAMES}.")