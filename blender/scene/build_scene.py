"""Build the INTERMEDIA residential complex through Blender MCP.

The scene is authored as a semantic hierarchy instead of a flat collection of
decorative meshes. Blender is the source of truth; this file is sent to the
connected Blender instance by ``scripts/run_blender_mcp.py``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


PROJECT_ROOT = Path("/Users/cristianexer/Hyperdrive/residential")
EXPORT_DIR = PROJECT_ROOT / "dist" / "assets"
BLEND_PATH = PROJECT_ROOT / "blender" / "exports" / "intermedia-residential.blend"
GLB_PATH = EXPORT_DIR / "intermedia-residential.glb"
MANIFEST_PATH = EXPORT_DIR / "intermedia-residential.json"
SCENE_VERSION = "2.0.0"
BUILDING_WIDTH = 28.0
BUILDING_DEPTH = 13.0
FLOOR_HEIGHTS = (3.8, 3.1, 3.1, 3.1)
LEVEL_BASES = (0.0, 3.8, 6.9, 10.0)
TOTAL_HEIGHT = sum(FLOOR_HEIGHTS)
BUILDINGS = {"A": -4.0, "B": 18.0, "C": 40.0}

MATS: dict[str, bpy.types.Material] = {}
ROOT: bpy.types.Object


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def descendants(collection: bpy.types.Collection) -> set[bpy.types.Collection]:
    found = {collection}
    for child in collection.children:
        found |= descendants(child)
    return found


def clear_owned_scene() -> None:
    """Remove only the previous generated project, preserving user content."""
    old = bpy.data.collections.get("INTERMEDIA_PROJECT") or bpy.data.collections.get("RESIDENTIAL_COMPLEX")
    if not old:
        return
    owned_collections = descendants(old)
    owned_objects = [
        obj for obj in bpy.data.objects
        if any(collection in owned_collections for collection in obj.users_collection)
        or obj.get("intermedia_owned")
    ]
    for obj in owned_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in sorted(owned_collections, key=lambda value: len(value.name), reverse=True):
        if collection.name in bpy.data.collections:
            bpy.data.collections.remove(collection, do_unlink=True)


def make_collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(collection)
    return collection


def mark(obj: bpy.types.Object, role: str | None = None, **metadata: object) -> bpy.types.Object:
    obj["intermedia_owned"] = True
    obj["scene_version"] = SCENE_VERSION
    if role:
        obj["role"] = role
    for key, value in metadata.items():
        obj[key] = value
    return obj


def empty(
    name: str,
    collection: bpy.types.Collection,
    parent: bpy.types.Object | None = None,
    location: tuple[float, float, float] = (0.0, 0.0, 0.0),
    role: str | None = None,
    **metadata: object,
) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    collection.objects.link(obj)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.6
    if parent:
        obj.parent = parent
    obj.location = location
    return mark(obj, role, **metadata)


def make_texture_image(name: str, kind: str) -> bpy.types.Image:
    """Create a small packed image texture so the browser GLB contains maps."""
    size = 96
    image = bpy.data.images.new(name, width=size, height=size, alpha=False)
    pixels: list[float] = []
    for y in range(size):
        for x in range(size):
            if kind == "brick":
                row = y // 12
                offset = 18 if row % 2 else 0
                mortar = (y % 12 in (0, 1)) or ((x + offset) % 30 in (0, 1))
                base = (0.38, 0.12, 0.045) if mortar else (0.62, 0.22, 0.08)
                wobble = ((x * 17 + y * 7) % 9) / 255.0
                rgb = tuple(min(1.0, channel + wobble) for channel in base)
            elif kind == "wood":
                grain = 0.045 * math.sin((x + y * 0.18) / 4.0) + 0.03 * math.sin(y / 11.0)
                rgb = (0.47 + grain, 0.24 + grain * 0.6, 0.10 + grain * 0.3)
            elif kind == "asphalt":
                value = 0.12 + ((x * 13 + y * 19) % 17) / 900.0
                rgb = (value, value * 1.03, value * 1.08)
            elif kind == "tile":
                grout = (x % 24 in (0, 1)) or (y % 24 in (0, 1))
                rgb = (0.42, 0.40, 0.36) if grout else (0.73, 0.70, 0.63)
            else:
                value = 0.16 + ((x * 5 + y * 11) % 15) / 160.0
                rgb = (value * 0.48, value, value * 0.36)
            pixels.extend((*rgb, 1.0))
    image.pixels = pixels
    image.pack()
    return image


def material(
    name: str,
    color: tuple[float, float, float],
    roughness: float = 0.55,
    metallic: float = 0.0,
    texture_kind: str | None = None,
    alpha: float = 1.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, alpha)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    if "IOR" in shader.inputs:
        shader.inputs["IOR"].default_value = 1.45
    if "Transmission Weight" in shader.inputs and alpha < 1.0:
        shader.inputs["Transmission Weight"].default_value = 0.25
    if alpha < 1.0:
        shader.inputs["Alpha"].default_value = alpha
        try:
            mat.surface_render_method = "DITHERED"
        except Exception:
            pass
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    if texture_kind:
        image = make_texture_image(f"IMG-{name}", texture_kind)
        tex = nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.interpolation = "Linear"
        tex.extension = "REPEAT"
        tex.location = (-260.0, 80.0)
        links.new(tex.outputs["Color"], shader.inputs["Base Color"])
        mat["texture_kind"] = texture_kind
    mat["material_family"] = name
    mat["color_hex"] = "#%02X%02X%02X" % tuple(round(channel * 255) for channel in color)
    return mat


def assign_material(obj: bpy.types.Object, mat: bpy.types.Material | None) -> None:
    if mat and hasattr(obj.data, "materials"):
        obj.data.materials.append(mat)


def mesh_object(
    name: str,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    collection: bpy.types.Collection,
    parent: bpy.types.Object | None = None,
    mat: bpy.types.Material | None = None,
    role: str | None = None,
    bevel: float = 0.0,
    **metadata: object,
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    # Every procedural mesh gets a stable local UV projection.  Image textures
    # otherwise export correctly but arrive in the browser with no TEXCOORD_0.
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        normal = polygon.normal
        for loop_index in polygon.loop_indices:
            coordinate = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            if abs(normal.z) > 0.5:
                uv = (coordinate.x * 0.18, coordinate.y * 0.18)
            elif abs(normal.y) > 0.5:
                uv = (coordinate.x * 0.18, coordinate.z * 0.18)
            else:
                uv = (coordinate.y * 0.18, coordinate.z * 0.18)
            uv_layer.data[loop_index].uv = uv
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    if parent:
        obj.parent = parent
    assign_material(obj, mat)
    if bevel:
        modifier = obj.modifiers.new("Architectural edge softness", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    return mark(obj, role, **metadata)


def box(
    name: str,
    location: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    collection: bpy.types.Collection,
    parent: bpy.types.Object | None = None,
    mat: bpy.types.Material | None = None,
    role: str | None = None,
    bevel: float = 0.0,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    **metadata: object,
) -> bpy.types.Object:
    hx, hy, hz = (value / 2.0 for value in dimensions)
    vertices = [
        (-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
        (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz),
    ]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    obj = mesh_object(name, vertices, faces, collection, parent, mat, role, bevel, **metadata)
    obj.location = location
    obj.rotation_euler = rotation
    return obj


def cylinder(
    name: str,
    location: tuple[float, float, float],
    radius: float,
    depth: float,
    collection: bpy.types.Collection,
    parent: bpy.types.Object | None = None,
    mat: bpy.types.Material | None = None,
    vertices_count: int = 16,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    role: str | None = None,
    **metadata: object,
) -> bpy.types.Object:
    vertices: list[tuple[float, float, float]] = []
    for z in (-depth / 2.0, depth / 2.0):
        for index in range(vertices_count):
            angle = 2.0 * math.pi * index / vertices_count
            vertices.append((radius * math.cos(angle), radius * math.sin(angle), z))
    faces: list[tuple[int, ...]] = [tuple(range(vertices_count - 1, -1, -1)), tuple(range(vertices_count, vertices_count * 2))]
    for index in range(vertices_count):
        nxt = (index + 1) % vertices_count
        faces.append((index, nxt, nxt + vertices_count, index + vertices_count))
    obj = mesh_object(name, vertices, faces, collection, parent, mat, role, 0.0, **metadata)
    obj.location = location
    obj.rotation_euler = rotation
    return obj


def sphere(name: str, location: tuple[float, float, float], scale: tuple[float, float, float], collection: bpy.types.Collection, parent: bpy.types.Object | None, mat: bpy.types.Material, role: str) -> bpy.types.Object:
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0)
    obj = bpy.context.object
    obj.name = name
    for linked in list(obj.users_collection):
        linked.objects.unlink(obj)
    collection.objects.link(obj)
    if parent:
        obj.parent = parent
    obj.location = location
    obj.scale = scale
    assign_material(obj, mat)
    return mark(obj, role)


def wall_between_openings(prefix: str, total_width: float, height: float, thickness: float, openings: list[tuple[float, float]], axis: str, fixed: float, collection: bpy.types.Collection, parent: bpy.types.Object, mat: bpy.types.Material, role: str = "exterior_wall") -> None:
    """Build wall spans around openings so windows are actual voids."""
    cursor = -total_width / 2.0
    for index, (center, opening_width) in enumerate(sorted(openings)):
        left = center - opening_width / 2.0
        if left > cursor + 0.01:
            span = (cursor + left) / 2.0
            width = left - cursor
            dims = (width, thickness, height) if axis == "x" else (thickness, width, height)
            loc = (span, fixed, height / 2.0) if axis == "x" else (fixed, span, height / 2.0)
            box(f"{prefix}_Span_{index}", loc, dims, collection, parent, mat, role)
        cursor = center + opening_width / 2.0
    if cursor < total_width / 2.0 - 0.01:
        span = (cursor + total_width / 2.0) / 2.0
        width = total_width / 2.0 - cursor
        dims = (width, thickness, height) if axis == "x" else (thickness, width, height)
        loc = (span, fixed, height / 2.0) if axis == "x" else (fixed, span, height / 2.0)
        box(f"{prefix}_Span_End", loc, dims, collection, parent, mat, role)


def add_front_window(prefix: str, x: float, z: float, width: float, height: float, collection: bpy.types.Collection, parent: bpy.types.Object, floor_id: str) -> None:
    y = 0.0
    box(f"{prefix}_Glass", (x, y - 0.08, z), (width, 0.06, height), collection, parent, MATS["glass"], "window_glazing", 0.02, floor_id=floor_id, selectable=True)
    for suffix, loc, dims in [
        ("Top", (x, y - 0.15, z + height / 2.0), (width + 0.12, 0.08, 0.07)),
        ("Bottom", (x, y - 0.15, z - height / 2.0), (width + 0.12, 0.08, 0.07)),
        ("Left", (x - width / 2.0, y - 0.15, z), (0.07, 0.08, height + 0.12)),
        ("Right", (x + width / 2.0, y - 0.15, z), (0.07, 0.08, height + 0.12)),
    ]:
        box(f"{prefix}_Frame_{suffix}", loc, dims, collection, parent, MATS["frame"], "window_frame", 0.015, floor_id=floor_id)
    box(f"{prefix}_Curtain", (x, y - 0.19, z), (width * 0.32, 0.025, height * 0.86), collection, parent, MATS["curtain"], "window_curtain")


def add_side_window(prefix: str, y: float, z: float, width: float, height: float, x: float, collection: bpy.types.Collection, parent: bpy.types.Object, floor_id: str) -> None:
    box(f"{prefix}_Glass", (x + 0.08, y, z), (0.06, width, height), collection, parent, MATS["glass"], "window_glazing", 0.02, floor_id=floor_id)
    for suffix, loc, dims in [
        ("Top", (x + 0.15, y, z + height / 2.0), (0.08, width + 0.12, 0.07)),
        ("Bottom", (x + 0.15, y, z - height / 2.0), (0.08, width + 0.12, 0.07)),
        ("Left", (x + 0.15, y - width / 2.0, z), (0.08, 0.07, height + 0.12)),
        ("Right", (x + 0.15, y + width / 2.0, z), (0.08, 0.07, height + 0.12)),
    ]:
        box(f"{prefix}_Frame_{suffix}", loc, dims, collection, parent, MATS["frame"], "window_frame", 0.015, floor_id=floor_id)


def add_balcony(prefix: str, x: float, floor: bpy.types.Object, collection: bpy.types.Collection, floor_id: str) -> None:
    balcony = empty(prefix, collection, floor, (x, -BUILDING_DEPTH / 2.0 - 1.3, 0.0), "balcony", floor_id=floor_id, explosion_group="facade")
    box(f"{prefix}_Slab", (0.0, 0.0, 0.2), (5.0, 2.25, 0.3), collection, balcony, MATS["concrete"], "balcony_slab", 0.05, floor_id=floor_id)
    box(f"{prefix}_BrickParapet", (0.0, -1.1, 1.05), (5.0, 0.28, 1.35), collection, balcony, MATS["brick"], "balcony_parapet", 0.03, floor_id=floor_id)
    for side in (-1, 1):
        box(f"{prefix}_Side_{side}", (side * 2.4, 0.0, 1.0), (0.18, 2.2, 1.45), collection, balcony, MATS["frame"], "balcony_rail", 0.02, floor_id=floor_id)
    for rail_x in (-1.2, 0.0, 1.2):
        box(f"{prefix}_Rail_{rail_x}", (rail_x, 0.0, 1.55), (0.06, 2.15, 0.06), collection, balcony, MATS["frame"], "balcony_rail")


def add_stair_core(floor: bpy.types.Object, collection: bpy.types.Collection, floor_id: str) -> None:
    core = empty(f"{floor_id}_STAIR_CORE", collection, floor, (0.0, 0.8, 0.0), "circulation", floor_id=floor_id)
    for side in (-1, 1):
        box(f"{floor_id}_StairWall_{side}", (side * 1.8, 0.0, 1.35), (0.18, 4.8, 2.7), collection, core, MATS["concrete"], "stairwell_wall", 0.02)
        for index in range(5):
            cylinder(f"{floor_id}_RailPost_{side}_{index}", (side * 1.4, -1.7 + index * 0.75, 0.75), 0.035, 1.2, collection, core, MATS["frame"], 8, role="stair_handrail_post")
        box(f"{floor_id}_Handrail_{side}", (side * 1.4, 0.0, 1.35), (0.06, 3.8, 0.06), collection, core, MATS["frame"], "stair_handrail")
    for step in range(10):
        box(f"{floor_id}_Stair_{step:02d}", (-1.05 + (step % 2) * 2.1, -1.6 + step * 0.32, 0.16 + (step // 5) * 0.17), (1.65, 0.32, 0.18), collection, core, MATS["wood"], "stair_tread", 0.015)


def add_generic_layout(floor: bpy.types.Object, collection: bpy.types.Collection, block_id: str, floor_index: int) -> None:
    floor_id = f"BLK-{block_id}_F{floor_index}"
    add_stair_core(floor, collection, floor_id)
    for side, x in (("L", -8.8), ("R", 8.8)):
        unit = empty(f"{floor_id}_UNIT_{side}", collection, floor, (x, 0.8, 0.0), "apartment_shell", building_id=block_id, floor_id=floor_id, unit_kind="representative")
        box(f"{floor_id}_UnitFloor_{side}", (0.0, 0.0, 0.10), (8.0, 10.2, 0.16), collection, unit, MATS["wood_floor"], "apartment_floor", floor_id=floor_id)
        box(f"{floor_id}_UnitPartition_{side}", (0.0, 0.9, 1.45), (0.12, 6.2, 2.7), collection, unit, MATS["white"], "interior_partition", 0.02, floor_id=floor_id)
        box(f"{floor_id}_UnitBackWall_{side}", (0.0, 5.0, 1.45), (8.0, 0.14, 2.7), collection, unit, MATS["white"], "interior_partition", 0.02, floor_id=floor_id)
        box(f"{floor_id}_UnitEntry_{side}", (0.0, -4.95, 1.1), (1.1, 0.10, 2.2), collection, unit, MATS["wood_dark"], "interior_door")


def add_kitchen(prefix: str, location: tuple[float, float], collection: bpy.types.Collection, parent: bpy.types.Object, width: float) -> None:
    x, y = location
    box(f"{prefix}_Base", (x, y, 0.72), (width, 0.62, 0.72), collection, parent, MATS["kitchen"], "fitted_kitchen", 0.04)
    box(f"{prefix}_Counter", (x, y - 0.04, 1.13), (width + 0.12, 0.70, 0.12), collection, parent, MATS["wood"], "kitchen_counter", 0.025)
    box(f"{prefix}_Backsplash", (x, y - 0.33, 1.72), (width, 0.04, 0.82), collection, parent, MATS["glass_green"], "kitchen_backsplash")
    for index in range(max(2, int(width // 0.75))):
        px = x - width / 2.0 + 0.45 + index * 0.72
        box(f"{prefix}_Upper_{index}", (px, y + 0.08, 2.1), (0.62, 0.42, 0.75), collection, parent, MATS["white"], "kitchen_upper_cabinet", 0.025)
        box(f"{prefix}_Handle_{index}", (px, y - 0.16, 2.1), (0.22, 0.025, 0.025), collection, parent, MATS["frame"], "kitchen_handle")
    box(f"{prefix}_Sink", (x - width * 0.18, y - 0.06, 1.22), (0.65, 0.4, 0.06), collection, parent, MATS["ceramic"], "kitchen_sink", 0.02)
    cylinder(f"{prefix}_Tap", (x - width * 0.18, y - 0.07, 1.42), 0.035, 0.4, collection, parent, MATS["frame"], 10, rotation=(math.radians(90), 0.0, 0.0), role="kitchen_tap")
    box(f"{prefix}_Oven", (x + width * 0.25, y - 0.06, 0.72), (0.62, 0.62, 0.72), collection, parent, MATS["charcoal"], "kitchen_oven", 0.025)
    box(f"{prefix}_Fridge", (x + width / 2.0 - 0.37, y + 0.1, 1.55), (0.68, 0.62, 2.7), collection, parent, MATS["charcoal"], "refrigerator", 0.035)
    box(f"{prefix}_UnderLight", (x, y - 0.18, 1.77), (width - 0.25, 0.03, 0.04), collection, parent, MATS["warm_emission"], "under_cabinet_light")


def add_sofa(prefix: str, location: tuple[float, float], collection: bpy.types.Collection, parent: bpy.types.Object) -> None:
    x, y = location
    box(f"{prefix}_Seat", (x, y, 0.48), (2.25, 0.88, 0.42), collection, parent, MATS["sofa"], "sofa", 0.16)
    box(f"{prefix}_Back", (x, y + 0.32, 1.05), (2.25, 0.18, 1.0), collection, parent, MATS["sofa"], "sofa", 0.1)
    for dx in (-1.0, 1.0):
        box(f"{prefix}_Arm_{dx}", (x + dx, y, 0.85), (0.22, 0.88, 0.74), collection, parent, MATS["sofa"], "sofa", 0.08)
    for dx, mat in ((-0.52, MATS["duvet"]), (0.52, MATS["gold"])):
        box(f"{prefix}_Cushion_{dx}", (x + dx, y - 0.1, 0.78), (0.62, 0.55, 0.14), collection, parent, mat, "sofa_cushion", 0.06)


def add_bed(prefix: str, location: tuple[float, float], collection: bpy.types.Collection, parent: bpy.types.Object, width: float) -> None:
    x, y = location
    box(f"{prefix}_Frame", (x, y, 0.28), (width + 0.18, 2.05, 0.28), collection, parent, MATS["wood_dark"], "bed_frame", 0.04)
    box(f"{prefix}_Mattress", (x, y, 0.58), (width, 1.9, 0.28), collection, parent, MATS["white"], "bed_mattress", 0.08)
    box(f"{prefix}_Duvet", (x, y - 0.2, 0.78), (width - 0.1, 1.05, 0.12), collection, parent, MATS["duvet"], "bed_linen", 0.05)
    box(f"{prefix}_Headboard", (x, y + 0.98, 1.45), (width + 0.2, 0.14, 1.55), collection, parent, MATS["wood_dark"], "bed_headboard", 0.03)
    for dx in (-0.58, 0.58):
        box(f"{prefix}_Pillow_{dx}", (x + dx, y + 0.52, 0.82), (0.58, 0.45, 0.12), collection, parent, MATS["white"], "bed_pillow", 0.05)


def add_table(prefix: str, location: tuple[float, float], collection: bpy.types.Collection, parent: bpy.types.Object) -> None:
    x, y = location
    box(f"{prefix}_Top", (x, y, 0.95), (1.65, 0.95, 0.12), collection, parent, MATS["white"], "dining_table", 0.035)
    for dx in (-0.63, 0.63):
        for dy in (-0.32, 0.32):
            box(f"{prefix}_Leg_{dx}_{dy}", (x + dx, y + dy, 0.46), (0.07, 0.07, 0.9), collection, parent, MATS["frame"], "dining_table_leg")
    for index, dx in enumerate((-1.12, 1.12)):
        box(f"{prefix}_Chair_{index}_Seat", (x + dx, y, 0.57), (0.58, 0.58, 0.12), collection, parent, MATS["gold"], "dining_chair", 0.08)
        box(f"{prefix}_Chair_{index}_Back", (x + dx, y + 0.22, 1.02), (0.58, 0.10, 0.82), collection, parent, MATS["gold"], "dining_chair", 0.06)


def add_bathroom(prefix: str, location: tuple[float, float], collection: bpy.types.Collection, parent: bpy.types.Object, width: float, depth: float) -> None:
    x, y = location
    box(f"{prefix}_Floor", (x, y, 0.13), (width, depth, 0.12), collection, parent, MATS["tile"], "bathroom_floor")
    box(f"{prefix}_BackTile", (x, y + depth / 2.0, 1.45), (width, 0.10, 2.7), collection, parent, MATS["tile_speckle"], "bathroom_tile")
    box(f"{prefix}_SideTile", (x - width / 2.0, y, 1.45), (0.10, depth, 2.7), collection, parent, MATS["tile"], "bathroom_tile")
    box(f"{prefix}_Vanity", (x - 0.35, y + 0.45, 0.78), (0.95, 0.48, 0.68), collection, parent, MATS["white"], "bathroom_vanity", 0.04)
    box(f"{prefix}_Sink", (x - 0.35, y + 0.19, 1.18), (0.62, 0.34, 0.10), collection, parent, MATS["ceramic"], "bathroom_sink", 0.03)
    box(f"{prefix}_Mirror", (x - 0.35, y + 0.13, 2.0), (0.78, 0.05, 0.78), collection, parent, MATS["mirror"], "bathroom_mirror")
    box(f"{prefix}_Toilet", (x + 0.62, y + 0.3, 0.52), (0.66, 0.98, 0.58), collection, parent, MATS["ceramic"], "toilet", 0.12)
    box(f"{prefix}_ShowerGlass", (x + 0.62, y - 0.65, 1.32), (0.05, 1.2, 2.35), collection, parent, MATS["glass"], "shower_glass")
    cylinder(f"{prefix}_ShowerHead", (x + 0.62, y - 0.85, 2.15), 0.12, 0.05, collection, parent, MATS["frame"], 16, rotation=(math.radians(90), 0.0, 0.0), role="shower_fitting")


def add_rug(prefix: str, location: tuple[float, float], size: tuple[float, float], collection: bpy.types.Collection, parent: bpy.types.Object) -> None:
    box(prefix, (location[0], location[1], 0.11), (size[0], size[1], 0.025), collection, parent, MATS["rug"], "rug", 0.015)


def add_plant(prefix: str, location: tuple[float, float], collection: bpy.types.Collection, parent: bpy.types.Object, scale: float) -> None:
    cylinder(f"{prefix}_Pot", (location[0], location[1], 0.32 * scale), 0.22 * scale, 0.45 * scale, collection, parent, MATS["ceramic"], 12, role="interior_plant_pot")
    cylinder(f"{prefix}_Stem", (location[0], location[1], 0.85 * scale), 0.035 * scale, 0.9 * scale, collection, parent, MATS["trunk"], 8, role="interior_plant_stem")
    for index in range(5):
        angle = index * 1.25
        sphere(f"{prefix}_Leaf_{index}", (location[0] + math.cos(angle) * 0.22 * scale, location[1] + math.sin(angle) * 0.22 * scale, 1.2 * scale), (0.18 * scale, 0.12 * scale, 0.42 * scale), collection, parent, MATS["leaf"], "interior_plant_leaf")


def add_desk(prefix: str, location: tuple[float, float], collection: bpy.types.Collection, parent: bpy.types.Object) -> None:
    x, y = location
    box(f"{prefix}_Top", (x, y, 0.82), (1.4, 0.56, 0.10), collection, parent, MATS["wood"], "desk", 0.02)
    for dx in (-0.58, 0.58):
        box(f"{prefix}_Leg_{dx}", (x + dx, y, 0.4), (0.07, 0.07, 0.76), collection, parent, MATS["frame"], "desk_leg")
    box(f"{prefix}_Chair", (x, y - 0.48, 0.55), (0.52, 0.52, 0.1), collection, parent, MATS["white"], "desk_chair", 0.05)
    box(f"{prefix}_Monitor", (x, y + 0.02, 1.08), (0.62, 0.06, 0.36), collection, parent, MATS["screen"], "computer_monitor")


def add_curtain(prefix: str, location: tuple[float, float], collection: bpy.types.Collection, parent: bpy.types.Object, width: float, height: float) -> None:
    x, y = location
    box(f"{prefix}_Left", (x - width * 0.31, y, height / 2.0), (width * 0.18, 0.05, height), collection, parent, MATS["curtain"], "interior_curtain", 0.025)
    box(f"{prefix}_Right", (x + width * 0.31, y, height / 2.0), (width * 0.18, 0.05, height), collection, parent, MATS["curtain"], "interior_curtain", 0.025)
    cylinder(f"{prefix}_Track", (x, y, height + 0.06), 0.025, width, collection, parent, MATS["frame"], 10, rotation=(0.0, math.radians(90), 0.0), role="curtain_track")


def add_unit_envelope(prefix: str, unit: bpy.types.Object, collection: bpy.types.Collection, width: float, depth: float, unit_kind: str, usable_area: float, balcony_area: float) -> None:
    floor_id = unit.get("floor_id", "")
    box(f"{prefix}_Floor", (0.0, 0.0, 0.08), (width, depth, 0.14), collection, unit, MATS["wood_floor"], "apartment_floor", floor_id=floor_id, usable_area=usable_area)
    for side, x in (("L", -width / 2.0), ("R", width / 2.0)):
        box(f"{prefix}_Wall_{side}", (x, 0.0, 1.45), (0.12, depth, 2.75), collection, unit, MATS["white"], "interior_partition", 0.02)
    box(f"{prefix}_Wall_Back", (0.0, depth / 2.0, 1.45), (width, 0.12, 2.75), collection, unit, MATS["white"], "interior_partition", 0.02)
    balcony_width = 3.0 if unit_kind == "Studio" else 3.4
    balcony_depth = balcony_area / balcony_width
    balcony = empty(f"{prefix}_BALCONY", collection, unit, (0.0, -depth / 2.0 - balcony_depth / 2.0, 0.0), "balcony", balcony_area=balcony_area)
    box(f"{prefix}_BalconySlab", (0.0, 0.0, 0.15), (balcony_width, balcony_depth, 0.25), collection, balcony, MATS["concrete"], "balcony_slab", 0.04)
    box(f"{prefix}_BalconyParapet", (0.0, -balcony_depth / 2.0, 0.95), (balcony_width, 0.16, 1.35), collection, balcony, MATS["brick"], "balcony_parapet", 0.03)
    unit["unit_kind"] = unit_kind
    unit["usable_area_m2"] = usable_area
    unit["balcony_area_m2"] = balcony_area
    unit["inferred_layout"] = unit_kind != "Studio"


def add_detailed_units(floors: dict[tuple[str, int], bpy.types.Object], root_collection: bpy.types.Collection) -> None:
    specs = [("A", 1, "Studio", (-7.4, 0.55)), ("B", 2, "2Room", (-7.0, 0.55)), ("C", 3, "3Room", (-6.4, 0.55))]
    for block_id, floor_index, kind, origin in specs:
        floor = floors[(block_id, floor_index)]
        collection = make_collection(f"Detailed_{kind}", root_collection)
        unit = empty(f"UNIT-{kind.upper()}", collection, floor, (*origin, 0.0), "detailed_apartment", building_id=block_id, floor_id=f"BLK-{block_id}_F{floor_index}", unit_kind=kind, inspection_priority=1)
        if kind == "Studio":
            width, depth = 5.5, 30.30 / 5.5
            add_kitchen("STUDIO_Kitchen", (0.0, depth / 2.0 - 0.42), collection, unit, 3.7)
            add_sofa("STUDIO_Sofa", (-1.15, -0.45), collection, unit)
            add_table("STUDIO_Dining", (1.25, -0.50), collection, unit)
            add_bed("STUDIO_Bed", (1.15, 1.45), collection, unit, 1.55)
            add_bathroom("STUDIO_Bath", (-1.65, 1.7), collection, unit, 1.9, 2.15)
            box("STUDIO_TV", (0.0, depth / 2.0 - 0.10, 2.12), (1.65, 0.08, 0.9), collection, unit, MATS["screen"], "television", 0.03)
            add_rug("STUDIO_Rug", (-0.95, -0.65), (2.3, 1.7), collection, unit)
            add_plant("STUDIO_Plant", (-2.0, -1.55), collection, unit, 0.65)
            add_curtain("STUDIO_Curtain", (2.1, -depth / 2.0 + 0.06), collection, unit, 2.2, 2.1)
        elif kind == "2Room":
            width, depth = 7.0, 6.2
            add_kitchen("2ROOM_Kitchen", (-1.2, depth / 2.0 - 0.42), collection, unit, 4.0)
            add_sofa("2ROOM_Sofa", (-1.6, -1.2), collection, unit)
            add_table("2ROOM_Dining", (1.5, -1.05), collection, unit)
            add_bed("2ROOM_Bed", (1.75, 1.7), collection, unit, 1.6)
            add_bathroom("2ROOM_Bath", (-2.35, 1.65), collection, unit, 2.0, 2.2)
            box("2ROOM_Partition", (0.2, 1.25, 1.42), (0.12, 3.6, 2.75), collection, unit, MATS["white"], "interior_partition", 0.02)
            add_rug("2ROOM_Rug", (-1.45, -1.25), (2.5, 1.8), collection, unit)
            add_plant("2ROOM_Plant", (-2.7, -1.7), collection, unit, 0.72)
            add_desk("2ROOM_Desk", (2.15, -0.1), collection, unit)
        else:
            width, depth = 8.6, 6.5
            add_kitchen("3ROOM_Kitchen", (-2.0, depth / 2.0 - 0.42), collection, unit, 4.2)
            add_sofa("3ROOM_Sofa", (-2.1, -1.1), collection, unit)
            add_table("3ROOM_Dining", (0.6, -1.0), collection, unit)
            add_bed("3ROOM_BedA", (1.8, 1.65), collection, unit, 1.6)
            add_bed("3ROOM_BedB", (-0.4, 1.65), collection, unit, 1.45)
            add_bathroom("3ROOM_Bath", (-3.2, 1.6), collection, unit, 2.0, 2.2)
            box("3ROOM_PartitionA", (0.4, 1.25, 1.42), (0.12, 3.8, 2.75), collection, unit, MATS["white"], "interior_partition", 0.02)
            box("3ROOM_PartitionB", (2.2, 1.25, 1.42), (0.12, 3.8, 2.75), collection, unit, MATS["white"], "interior_partition", 0.02)
            add_rug("3ROOM_Rug", (-2.0, -1.15), (2.7, 1.9), collection, unit)
            add_plant("3ROOM_Plant", (-3.4, -1.65), collection, unit, 0.78)
            add_desk("3ROOM_Desk", (2.7, -0.2), collection, unit)
        add_unit_envelope(kind.upper(), unit, collection, width, depth, kind, {"Studio": 30.30, "2Room": 43.40, "3Room": 55.90}[kind], 6.60)


def add_building(block_id: str, center_y: float, root_collection: bpy.types.Collection) -> dict[int, bpy.types.Object]:
    block_collection = make_collection(f"Block_{block_id}", root_collection)
    block = empty(f"BLK-{block_id}", block_collection, ROOT, (0.0, center_y, 0.0), "building", building_id=block_id, levels="P+3", explosion_group="building")
    block["front_direction"] = "-Y Blender / +Z glTF"
    floors: dict[int, bpy.types.Object] = {}
    for floor_index, (base_z, floor_height) in enumerate(zip(LEVEL_BASES, FLOOR_HEIGHTS)):
        floor_id = f"BLK-{block_id}_F{floor_index}"
        floor_collection = make_collection(f"Block_{block_id}_Floor_{floor_index}", block_collection)
        floor = empty(floor_id, floor_collection, block, (0.0, 0.0, base_z), "floor", building_id=block_id, floor_index=floor_index, floor_id=floor_id, explosion_group="floor")
        floors[floor_index] = floor
        box(f"{floor_id}_Slab", (0.0, 0.0, 0.04), (BUILDING_WIDTH, BUILDING_DEPTH, 0.22), floor_collection, floor, MATS["concrete"], "floor_slab", 0.04, building_id=block_id, floor_id=floor_id)
        box(f"{floor_id}_Ceiling", (0.0, 0.0, floor_height - 0.06), (BUILDING_WIDTH - 0.1, BUILDING_DEPTH - 0.1, 0.12), floor_collection, floor, MATS["ceiling"], "ceiling", 0.025, building_id=block_id, floor_id=floor_id)
        facade = empty(f"{floor_id}_FACADE_FRONT", floor_collection, floor, (0.0, -BUILDING_DEPTH / 2.0 - 0.08, 0.0), "facade", building_id=block_id, floor_id=floor_id, facade_side="front", explosion_group="facade")
        back = empty(f"{floor_id}_FACADE_BACK", floor_collection, floor, (0.0, BUILDING_DEPTH / 2.0 + 0.08, 0.0), "facade", building_id=block_id, floor_id=floor_id, facade_side="back", explosion_group="facade")
        left = empty(f"{floor_id}_FACADE_LEFT", floor_collection, floor, (-BUILDING_WIDTH / 2.0 - 0.08, 0.0, 0.0), "facade", building_id=block_id, floor_id=floor_id, facade_side="left", explosion_group="facade")
        right = empty(f"{floor_id}_FACADE_RIGHT", floor_collection, floor, (BUILDING_WIDTH / 2.0 + 0.08, 0.0, 0.0), "facade", building_id=block_id, floor_id=floor_id, facade_side="right", explosion_group="facade")
        if floor_index == 0:
            openings = [(-11.0, 3.0), (-7.0, 3.0), (-3.6, 3.1), (3.6, 3.1), (7.0, 3.0), (11.0, 3.0)]
            win_z, win_h = 1.78, 2.25
        else:
            openings = [(-11.3, 3.0), (-7.0, 2.6), (-3.3, 2.1), (3.3, 2.1), (7.0, 2.6), (11.3, 3.0)]
            win_z, win_h = floor_height / 2.0 + 0.25, 1.55
        wall_between_openings(f"{floor_id}_FrontWall", BUILDING_WIDTH, floor_height, 0.24, openings, "x", 0.0, floor_collection, facade, MATS["white"])
        for index, (x, width) in enumerate(openings):
            add_front_window(f"{floor_id}_FrontWindow_{index}", x, win_z, width - 0.2, win_h, floor_collection, facade, floor_id)
        back_openings = [(-10.8, 2.6), (-6.0, 2.6), (6.0, 2.6), (10.8, 2.6)]
        wall_between_openings(f"{floor_id}_BackWall", BUILDING_WIDTH, floor_height, 0.24, back_openings, "x", 0.0, floor_collection, back, MATS["white"])
        for index, (x, width) in enumerate(back_openings):
            add_front_window(f"{floor_id}_BackWindow_{index}", x, win_z, width - 0.2, win_h, floor_collection, back, floor_id)
        side_openings = [(-4.5, 2.2), (0.0, 2.2), (4.5, 2.2)]
        wall_between_openings(f"{floor_id}_LeftWall", BUILDING_DEPTH, floor_height, 0.24, side_openings, "y", 0.0, floor_collection, left, MATS["white"])
        wall_between_openings(f"{floor_id}_RightWall", BUILDING_DEPTH, floor_height, 0.24, side_openings, "y", 0.0, floor_collection, right, MATS["white"])
        for index, (y, width) in enumerate(side_openings):
            add_side_window(f"{floor_id}_SideL_{index}", y, win_z, width - 0.18, win_h, 0.0, floor_collection, left, floor_id)
            add_side_window(f"{floor_id}_SideR_{index}", y, win_z, width - 0.18, win_h, 0.0, floor_collection, right, floor_id)
        panel = empty(f"{floor_id}_GRAPHITE_PANEL", floor_collection, facade, (0.0, -0.08, 0.0), "facade_panel", building_id=block_id, floor_id=floor_id, facade_side="front", explosion_group="facade")
        if floor_index == 0:
            box(f"{floor_id}_GroundBand", (0.0, 0.0, 1.1), (BUILDING_WIDTH - 0.2, 0.2, 2.2), floor_collection, panel, MATS["charcoal"], "ground_floor_band", 0.02)
        else:
            box(f"{floor_id}_GraphiteField", (0.0, 0.02, floor_height / 2.0), (12.6, 0.12, floor_height - 0.18), floor_collection, panel, MATS["graphite"], "graphite_facade_field")
            for x in (-3.3, 3.3):
                box(f"{floor_id}_WhiteTrim_{x}", (x, -0.08, floor_height / 2.0), (2.6, 0.13, 2.15), floor_collection, panel, MATS["trim"], "facade_trim", 0.025)
        if floor_index > 0:
            add_balcony(f"{floor_id}_BALCONY_L", -10.0, floor, floor_collection, floor_id)
            add_balcony(f"{floor_id}_BALCONY_R", 10.0, floor, floor_collection, floor_id)
        add_generic_layout(floor, floor_collection, block_id, floor_index)

    roof_collection = make_collection(f"Block_{block_id}_Roof", block_collection)
    roof = empty(f"BLK-{block_id}_ROOF", roof_collection, block, (0.0, 0.0, TOTAL_HEIGHT), "roof", building_id=block_id, explosion_group="roof")
    box(f"BLK-{block_id}_RoofSouth", (0.0, -3.25, 0.38), (30.3, 6.8, 0.28), roof_collection, roof, MATS["roof"], "roof_surface", 0.04, rotation=(math.radians(5.0), 0.0, 0.0))
    box(f"BLK-{block_id}_RoofNorth", (0.0, 3.25, 0.38), (30.3, 6.8, 0.28), roof_collection, roof, MATS["roof"], "roof_surface", 0.04, rotation=(math.radians(-5.0), 0.0, 0.0))
    for index in range(-6, 7):
        box(f"BLK-{block_id}_RoofRib_{index}", (index * 2.25, -3.25, 0.58), (0.06, 6.6, 0.06), roof_collection, roof, MATS["frame"], "roof_seam", rotation=(math.radians(5.0), 0.0, 0.0))
    for y in (-6.75, 6.75):
        box(f"BLK-{block_id}_Gutter_{y}", (0.0, y, 0.05), (30.6, 0.18, 0.18), roof_collection, roof, MATS["frame"], "roof_gutter", 0.03)
    for x in (-13.7, 13.7):
        box(f"BLK-{block_id}_Downpipe_{x}", (x, -6.72, -6.4), (0.12, 0.12, 12.8), roof_collection, roof, MATS["frame"], "roof_downpipe")
    entrance = empty(f"BLK-{block_id}_ENTRANCE", block_collection, floors[0], (0.0, -7.0, 0.0), "entrance", building_id=block_id, floor_id=f"BLK-{block_id}_F0")
    box(f"BLK-{block_id}_EntryGlass", (0.0, -0.1, 1.35), (2.6, 0.12, 2.55), block_collection, entrance, MATS["glass_dark"], "entrance_glazing", 0.03)
    box(f"BLK-{block_id}_EntryCanopy", (0.0, -1.0, 2.7), (4.8, 1.7, 0.22), block_collection, entrance, MATS["concrete"], "entrance_canopy", 0.04)
    for step in range(3):
        box(f"BLK-{block_id}_EntryStep_{step}", (0.0, -0.52 - step * 0.38, 0.10 + step * 0.08), (4.2 - step * 0.2, 0.38, 0.16), block_collection, entrance, MATS["concrete"], "entrance_step", 0.025)
    for x in (-1.9, 1.9):
        cylinder(f"BLK-{block_id}_CanopyPost_{x}", (x, -1.0, 1.35), 0.06, 2.7, block_collection, entrance, MATS["frame"], 10, role="entrance_post")
    return floors


def add_car(prefix: str, location: tuple[float, float], rotation: float, body_mat: bpy.types.Material, collection: bpy.types.Collection, parent: bpy.types.Object) -> None:
    x, y = location
    car = empty(prefix, collection, parent, (x, y, 0.0), "vehicle", vehicle_class="compact")
    box(f"{prefix}_Body", (0.0, 0.0, 0.52), (4.1, 1.75, 0.68), collection, car, body_mat, "vehicle_body", 0.12, rotation=(0.0, 0.0, rotation))
    box(f"{prefix}_Cabin", (0.1, 0.02, 0.98), (2.25, 1.42, 0.54), collection, car, MATS["glass_dark"], "vehicle_glazing", 0.10, rotation=(0.0, 0.0, rotation))
    box(f"{prefix}_Hood", (-1.35, -0.02, 0.78), (0.8, 1.55, 0.16), collection, car, body_mat, "vehicle_body", 0.06, rotation=(0.0, 0.0, rotation))
    for index, (dx, dy) in enumerate(((-1.3, -0.88), (-1.3, 0.88), (1.3, -0.88), (1.3, 0.88))):
        cylinder(f"{prefix}_Wheel_{index}", (dx, dy, 0.36), 0.34, 0.18, collection, car, MATS["rubber"], 16, rotation=(math.pi / 2.0, 0.0, rotation), role="vehicle_wheel")
    for index, dy in enumerate((-0.54, 0.54)):
        box(f"{prefix}_Headlight_{index}", (-2.04, dy, 0.62), (0.06, 0.28, 0.18), collection, car, MATS["headlight"], "vehicle_light", 0.02, rotation=(0.0, 0.0, rotation))


def add_tree(prefix: str, location: tuple[float, float], scale: float, collection: bpy.types.Collection, parent: bpy.types.Object) -> None:
    x, y = location
    tree = empty(prefix, collection, parent, (x, y, 0.0), "landscape_tree")
    cylinder(f"{prefix}_Trunk", (0.0, 0.0, 1.8 * scale), 0.18 * scale, 3.6 * scale, collection, tree, MATS["trunk"], 10, role="tree_trunk")
    for index, offset in enumerate(((0.0, 0.0, 3.55), (-0.6, 0.1, 4.15), (0.55, 0.15, 4.2), (0.0, -0.45, 4.65))):
        sphere(f"{prefix}_Canopy_{index}", (offset[0] * scale, offset[1] * scale, offset[2] * scale), (1.45 * scale, 1.25 * scale, 1.55 * scale), collection, tree, MATS["leaf" if index % 2 else "leaf_dark"], "tree_canopy")


def add_site(root_collection: bpy.types.Collection) -> None:
    site_collection = make_collection("Site_Context", root_collection)
    site = empty("SITE", site_collection, ROOT, (0.0, 0.0, 0.0), "site")
    box("SITE_Terrain", (0.0, 14.0, -0.34), (120.0, 104.0, 0.55), site_collection, site, MATS["grass"], "site_ground", 0.25)
    box("SITE_Court", (0.0, 12.0, -0.01), (62.0, 84.0, 0.18), site_collection, site, MATS["asphalt"], "access_court")
    box("SITE_Street", (0.0, -35.0, 0.0), (120.0, 5.2, 0.20), site_collection, site, MATS["asphalt"], "public_street")
    box("SITE_Sidewalk", (0.0, -31.8, 0.12), (120.0, 1.8, 0.16), site_collection, site, MATS["paving"], "sidewalk")
    for y in (-26.0, -18.0, 4.0, 26.0, 48.0):
        box(f"SITE_Lane_{y}", (0.0, y, 0.08), (58.0, 4.0, 0.16), site_collection, site, MATS["asphalt"], "access_lane")
    for row_y in (-27.0, -20.0, 1.0, 23.0, 45.0):
        for index in range(-5, 6):
            box(f"SITE_ParkingLine_{row_y}_{index}", (index * 5.0, row_y, 0.09), (0.08, 5.2, 0.025), site_collection, site, MATS["road_line"], "parking_marking")
    for x, y, width in ((-23.0, -29.0, 7.0), (23.0, -29.0, 7.0), (-25.0, 14.0, 6.0), (25.0, 36.0, 6.0)):
        box(f"SITE_PlantingIsland_{x}_{y}", (x, y, 0.14), (width, 4.6, 0.12), site_collection, site, MATS["grass_bright"], "planted_island", 0.28)
    for side in (-1, 1):
        for index in range(-6, 7):
            cylinder(f"SITE_FencePost_{side}_{index}", (index * 9.0, side * 39.5, 1.0), 0.035, 2.0, site_collection, site, MATS["frame"], 8, role="perimeter_fence")
        box(f"SITE_FenceRail_{side}", (0.0, side * 39.5, 1.4), (112.0, 0.04, 0.06), site_collection, site, MATS["frame"], "perimeter_fence")
    positions = [
        (-23, -24, 0.0), (-15, -24, 0.0), (-7, -24, 0.0), (2, -24, 0.0), (10, -24, 0.0), (19, -24, 0.0),
        (-25, 2, math.pi / 2), (25, 2, -math.pi / 2), (-25, 24, math.pi / 2), (25, 24, -math.pi / 2),
        (-25, 46, math.pi / 2), (25, 46, -math.pi / 2), (-18, -18, math.pi), (18, -18, math.pi),
    ]
    colors = [MATS["car_red"], MATS["car_white"], MATS["car_blue"], MATS["car_yellow"], MATS["car_silver"], MATS["car_dark"]]
    for index, (x, y, rotation) in enumerate(positions):
        add_car(f"CAR_{index:02d}", (x, y), rotation, colors[index % len(colors)], site_collection, site)
    trees = [(-49, -27, 1.4), (-47, -7, 1.15), (-49, 16, 1.35), (-47, 42, 1.5), (49, -27, 1.3), (48, -6, 1.1), (49, 15, 1.45), (47, 37, 1.2), (48, 56, 1.5), (-33, 57, 1.0), (-15, 58, 1.2), (16, 58, 1.05), (33, 57, 1.25)]
    for index, (x, y, scale) in enumerate(trees):
        add_tree(f"TREE_{index:02d}", (x, y), scale, site_collection, site)
    for index, x in enumerate((-29.0, 29.0)):
        box(f"SITE_Bin_{index}", (x, -29.4, 0.65), (1.1, 1.1, 1.3), site_collection, site, MATS["charcoal"], "site_bin", 0.08)
        box(f"SITE_BinLid_{index}", (x, -29.4, 1.36), (1.2, 1.2, 0.08), site_collection, site, MATS["frame"], "site_bin")
    box("SITE_EntranceSign", (0.0, -30.4, 1.4), (5.2, 0.12, 1.8), site_collection, site, MATS["white"], "site_sign", 0.06)
    box("SITE_EntranceSignBand", (0.0, -30.48, 1.55), (4.7, 0.05, 0.36), site_collection, site, MATS["blue"], "site_sign")


def add_collision_geometry(root_collection: bpy.types.Collection) -> None:
    collection = make_collection("Collision_Proxy", root_collection)
    collision_root = empty("COLLISION", collection, ROOT, (0.0, 0.0, 0.0), "collision_root")
    box("COLLISION_SiteBoundary", (0.0, 14.0, -0.4), (120.0, 104.0, 0.4), collection, collision_root, None, "collision", export_collision=False)
    for block_id, center_y in BUILDINGS.items():
        block = empty(f"COLLISION_BLK-{block_id}", collection, collision_root, (0.0, center_y, 0.0), "collision", building_id=block_id)
        for side, location, dims in (
            ("Back", (0.0, BUILDING_DEPTH / 2.0, TOTAL_HEIGHT / 2.0), (BUILDING_WIDTH, 0.24, TOTAL_HEIGHT)),
            ("Left", (-BUILDING_WIDTH / 2.0, 0.0, TOTAL_HEIGHT / 2.0), (0.24, BUILDING_DEPTH, TOTAL_HEIGHT)),
            ("Right", (BUILDING_WIDTH / 2.0, 0.0, TOTAL_HEIGHT / 2.0), (0.24, BUILDING_DEPTH, TOTAL_HEIGHT)),
        ):
            box(f"COLLISION_BLK-{block_id}_{side}", location, dims, collection, block, None, "collision", export_collision=False)
        # Leave a generous portal at the front entrance so the eye-level
        # controller can enter the lobby without disabling the building shell.
        portal_width = 3.2
        side_width = (BUILDING_WIDTH - portal_width) / 2.0
        front_y = -BUILDING_DEPTH / 2.0
        box(f"COLLISION_BLK-{block_id}_FrontL", (-(portal_width + side_width) / 2.0, front_y, TOTAL_HEIGHT / 2.0), (side_width, 0.24, TOTAL_HEIGHT), collection, block, None, "collision", export_collision=False)
        box(f"COLLISION_BLK-{block_id}_FrontR", ((portal_width + side_width) / 2.0, front_y, TOTAL_HEIGHT / 2.0), (side_width, 0.24, TOTAL_HEIGHT), collection, block, None, "collision", export_collision=False)


def setup_scene(root_collection: bpy.types.Collection) -> None:
    scene = bpy.context.scene
    scene.name = "INTERMEDIA Residential Complex"
    scene["scene_version"] = SCENE_VERSION
    scene["project_name"] = "INTERMEDIA Residential Complex"
    scene["building_count"] = 3
    scene["building_levels"] = "P+3"
    scene["source_note"] = "Reference-based illustrative model; missing layouts are inferred"
    scene["verified_studio_area_m2"] = 30.30
    scene["verified_studio_balcony_m2"] = 6.60
    scene["parking_note"] = "One above-ground parking space per apartment in the supplied brief"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 60
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.55, 0.72, 0.92)
    background = scene.world.node_tree.nodes.get("Background") if scene.world and scene.world.use_nodes else None
    if background:
        background.inputs["Color"].default_value = (0.42, 0.62, 0.88, 1.0)
        background.inputs["Strength"].default_value = 0.55
    camera_data = bpy.data.cameras.new("CAM-Overview_Data")
    camera = bpy.data.objects.new("CAM-Overview", camera_data)
    root_collection.objects.link(camera)
    camera.location = (59.0, -72.0, 48.0)
    camera_data.lens = 46
    camera_data.clip_end = 500.0
    target = Vector((0.0, 14.0, 5.5))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    mark(camera, "overview_camera", camera_id="overview")
    sun_data = bpy.data.lights.new("LGT-DaySun_Data", "SUN")
    sun_data.energy = 3.2
    sun_data.angle = math.radians(18.0)
    sun = bpy.data.objects.new("LGT-DaySun", sun_data)
    root_collection.objects.link(sun)
    sun.rotation_euler = (math.radians(28.0), math.radians(-24.0), math.radians(-35.0))
    mark(sun, "sun_light", light_id="daylight")
    fill_data = bpy.data.lights.new("LGT-CourtFill_Data", "AREA")
    fill_data.energy = 950.0
    fill_data.shape = "DISK"
    fill_data.size = 32.0
    fill = bpy.data.objects.new("LGT-CourtFill", fill_data)
    root_collection.objects.link(fill)
    fill.location = (0.0, -12.0, 34.0)
    mark(fill, "fill_light")


def build_manifest() -> None:
    manifest = {
        "schemaVersion": 1,
        "sceneVersion": SCENE_VERSION,
        "units": "meters",
        "coordinateSystem": "Blender Z-up authoring, glTF Y-up export",
        "source": "INTERMEDIA reference renders and supplied marketing brief",
        "release": {
            "browserModel": "assets/intermedia-residential.glb",
            "sceneSource": "../blender/exports/intermedia-residential.blend",
            "manifest": "assets/intermedia-residential.json",
            "licenses": "assets/licenses.json",
            "collision": "Embedded nodes with role=collision; browser builds AABBs at load time",
            "bakedLighting": None,
        },
        "bounds": {
            "siteMeters": {"min": [-60.0, -38.0, -0.62], "max": [60.0, 66.0, -0.06]},
            "buildingFootprintMeters": {"width": BUILDING_WIDTH, "depth": BUILDING_DEPTH, "height": TOTAL_HEIGHT + 0.9},
        },
        "lighting": {"daySunNode": "LGT-DaySun", "browserSunIntensity": 35, "interiorBaking": "not bundled; browser uses authored materials and viewer lights"},
        "verified": {"studioUsableAreaM2": 30.30, "studioBalconyAreaM2": 6.60, "buildingLevels": "P+3", "buildingCount": 3},
        "inferred": {"twoRoomAndThreeRoomAreas": True, "roomPartitions": True, "siteContext": True},
        "buildings": [{"id": key, "centerY": value, "levels": [0, 1, 2, 3]} for key, value in BUILDINGS.items()],
        "apartments": {
            "Studio": {"building": "A", "floor": 1, "usableAreaM2": 30.30, "balconyAreaM2": 6.60, "inferred": False},
            "2Room": {"building": "B", "floor": 2, "usableAreaM2": 43.40, "balconyAreaM2": 6.60, "inferred": True},
            "3Room": {"building": "C", "floor": 3, "usableAreaM2": 55.90, "balconyAreaM2": 6.60, "inferred": True},
        },
        "viewpoints": {"overview": {"position": [59, -72, 48], "target": [0, 14, 5.5]}, "courtyard": {"position": [31, -22, 5.8], "target": [0, 2, 4.8]}, "facade": {"position": [29, -31, 11.5], "target": [0, -4, 6.3]}},
        "roles": ["building", "floor", "floor_slab", "ceiling", "facade", "facade_panel", "window_glazing", "apartment_shell", "detailed_apartment", "balcony", "roof", "circulation", "vehicle", "landscape_tree", "collision"],
    }
    ensure_dir(MANIFEST_PATH.parent)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def create_materials() -> None:
    global MATS
    MATS = {
        "white": material("MAT-Plaster-White", (0.82, 0.84, 0.83), 0.72),
        "trim": material("MAT-Trim-WarmWhite", (0.96, 0.94, 0.87), 0.58),
        "graphite": material("MAT-Plaster-Graphite", (0.15, 0.17, 0.19), 0.62),
        "charcoal": material("MAT-Ground-Charcoal", (0.045, 0.052, 0.060), 0.68),
        "brick": material("MAT-Brick-Warm", (0.56, 0.19, 0.07), 0.82, texture_kind="brick"),
        "concrete": material("MAT-Concrete", (0.50, 0.53, 0.50), 0.88),
        "roof": material("MAT-Roof-Graphite", (0.025, 0.032, 0.040), 0.58),
        "frame": material("MAT-Frame-Dark", (0.035, 0.045, 0.055), 0.30, 0.45),
        "glass": material("MAT-Glass-Cool", (0.10, 0.28, 0.38), 0.14, 0.08, alpha=0.62),
        "glass_dark": material("MAT-Glass-Dark", (0.025, 0.055, 0.070), 0.12, 0.25, alpha=0.8),
        "curtain": material("MAT-Curtain-Warm", (0.68, 0.47, 0.28), 0.95),
        "asphalt": material("MAT-Asphalt", (0.055, 0.065, 0.075), 0.92, texture_kind="asphalt"),
        "paving": material("MAT-Paving", (0.46, 0.48, 0.46), 0.85),
        "road_line": material("MAT-Road-Line", (0.88, 0.85, 0.75), 0.68),
        "grass": material("MAT-Grass-Base", (0.06, 0.13, 0.07), 0.96, texture_kind="grass"),
        "grass_bright": material("MAT-Grass-Bright", (0.16, 0.34, 0.11), 0.92, texture_kind="grass"),
        "trunk": material("MAT-Tree-Trunk", (0.18, 0.075, 0.028), 0.98),
        "leaf": material("MAT-Tree-Leaf", (0.04, 0.20, 0.06), 0.96),
        "leaf_dark": material("MAT-Tree-Leaf-Dark", (0.018, 0.085, 0.035), 0.98),
        "rubber": material("MAT-Rubber", (0.008, 0.012, 0.015), 0.90),
        "headlight": material("MAT-Headlight", (0.94, 0.82, 0.51), 0.18),
        "car_red": material("MAT-Car-Red", (0.56, 0.045, 0.025), 0.30, 0.16),
        "car_white": material("MAT-Car-White", (0.75, 0.78, 0.76), 0.28, 0.12),
        "car_blue": material("MAT-Car-Blue", (0.055, 0.22, 0.42), 0.28, 0.18),
        "car_yellow": material("MAT-Car-Yellow", (0.70, 0.48, 0.035), 0.30, 0.12),
        "car_silver": material("MAT-Car-Silver", (0.42, 0.46, 0.49), 0.24, 0.30),
        "car_dark": material("MAT-Car-Dark", (0.055, 0.07, 0.09), 0.25, 0.26),
        "wood_floor": material("MAT-Interior-WoodFloor", (0.50, 0.28, 0.12), 0.76, texture_kind="wood"),
        "wood": material("MAT-Interior-Wood", (0.38, 0.18, 0.07), 0.66, texture_kind="wood"),
        "wood_dark": material("MAT-Interior-WoodDark", (0.07, 0.035, 0.025), 0.70),
        "kitchen": material("MAT-Interior-Kitchen", (0.82, 0.84, 0.80), 0.45),
        "glass_green": material("MAT-Interior-GlassGreen", (0.16, 0.42, 0.35), 0.22, 0.08),
        "sofa": material("MAT-Interior-Sofa", (0.14, 0.15, 0.17), 0.90),
        "gold": material("MAT-Interior-Gold", (0.72, 0.46, 0.04), 0.52),
        "duvet": material("MAT-Interior-Duvet", (0.035, 0.045, 0.055), 0.92),
        "tile": material("MAT-Interior-Tile", (0.49, 0.46, 0.41), 0.62, texture_kind="tile"),
        "tile_speckle": material("MAT-Interior-Tile-Speckle", (0.64, 0.62, 0.56), 0.72, texture_kind="tile"),
        "ceramic": material("MAT-Interior-Ceramic", (0.88, 0.87, 0.80), 0.28),
        "mirror": material("MAT-Interior-Mirror", (0.16, 0.23, 0.25), 0.06, 0.65),
        "screen": material("MAT-Interior-Screen", (0.005, 0.007, 0.009), 0.18, 0.20),
        "ceiling": material("MAT-Interior-Ceiling", (0.90, 0.90, 0.87), 0.92),
        "rug": material("MAT-Interior-Rug", (0.12, 0.18, 0.22), 0.96),
        "blue": material("MAT-INTERMEDIA-Blue", (0.0, 0.176, 0.588), 0.52),
        "warm_emission": material("MAT-Warm-Interior-Light", (1.0, 0.52, 0.18), 0.35),
    }


def export_files() -> None:
    ensure_dir(EXPORT_DIR)
    ensure_dir(BLEND_PATH.parent)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    bpy.ops.export_scene.gltf(filepath=str(GLB_PATH), export_format="GLB", export_apply=False, export_materials="EXPORT", export_extras=True, export_lights=True, export_cameras=True)


def main() -> dict[str, object]:
    clear_owned_scene()
    create_materials()
    root_collection = make_collection("INTERMEDIA_PROJECT")
    global ROOT
    ROOT = empty("INTERMEDIA_PROJECT", root_collection, None, (0.0, 0.0, 0.0), "project", project_id="intermedia-residential", scene_version=SCENE_VERSION)
    add_site(root_collection)
    floors: dict[tuple[str, int], bpy.types.Object] = {}
    for block_id, center_y in BUILDINGS.items():
        for floor_index, floor in add_building(block_id, center_y, root_collection).items():
            floors[(block_id, floor_index)] = floor
    detailed_collection = make_collection("Detailed_Apartments", root_collection)
    add_detailed_units(floors, detailed_collection)
    add_collision_geometry(root_collection)
    setup_scene(root_collection)
    build_manifest()
    export_files()
    owned_meshes = sum(1 for obj in bpy.data.objects if obj.type == "MESH" and obj.get("intermedia_owned"))
    return {"status": "built", "scene_version": SCENE_VERSION, "blend_path": str(BLEND_PATH), "glb_path": str(GLB_PATH), "manifest_path": str(MANIFEST_PATH), "owned_meshes": owned_meshes, "owned_objects": sum(1 for obj in bpy.data.objects if obj.get("intermedia_owned")), "materials": len(MATS), "textures": sum(1 for image in bpy.data.images if image.name.startswith("IMG-")), "buildings": list(BUILDINGS), "detailed_apartments": ["Studio", "2Room", "3Room"]}


result = main()
