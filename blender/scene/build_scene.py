"""Build the INTERMEDIA residential complex through Blender MCP.

The scene is authored as a semantic hierarchy instead of a flat collection of
decorative meshes. Blender is the source of truth; this file is sent to the
connected Blender instance by ``scripts/run_blender_mcp.py``.
"""

from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


PROJECT_ROOT = Path(__file__).resolve().parents[2]
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
SLAB_THICKNESS = 0.22
FINISH_BOTTOM = 0.02
FINISH_TOP = 0.08
COURT_TOP = 0.08
BAY_WIDTH = 2.5
BAY_LENGTH = 5.0
DETAILED_FLOORS = {("A", 1), ("B", 2), ("C", 3)}
# Physical size covered by one repeat, in metres (not one scale for all maps).
TEXTURE_METERS = {"brick": (0.96, 0.60), "wood": (0.72, 2.4), "tile": (2.4, 2.4), "asphalt": (0.8, 0.8), "grass": (1.2, 1.2)}

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
    roots = [collection for collection in bpy.data.collections if collection.get("intermedia_owned") or collection.name in ("INTERMEDIA_PROJECT", "RESIDENTIAL_COMPLEX")]
    candidates = set().union(*(descendants(root) for root in roots))
    owned_collections = {collection for collection in candidates if collection.get("intermedia_owned") or collection.name in ("INTERMEDIA_PROJECT", "RESIDENTIAL_COMPLEX", "Site_Context", "Collision_Proxy") or collection.name.startswith(("Block_", "Detailed_"))}
    for collection in candidates - owned_collections:
        if collection.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(collection)
        for parent in owned_collections:
            if collection.name in parent.children:
                parent.children.unlink(collection)
    # Collection membership alone is not ownership: users may link their own
    # objects into the generated hierarchy. Keep those, including world pose.
    owned_objects = [obj for obj in bpy.data.objects if obj.get("intermedia_owned")]
    for obj in list(bpy.data.objects):
        if obj.get("intermedia_owned"):
            continue
        if obj.parent in owned_objects:
            world = obj.matrix_world.copy()
            obj.parent = None
            obj.matrix_world = world
        if obj.users_collection and all(c in owned_collections for c in obj.users_collection):
            bpy.context.scene.collection.objects.link(obj)
        for collection in list(obj.users_collection):
            if collection in owned_collections:
                collection.objects.unlink(obj)
    for obj in owned_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    # Remove leaves only; do not unlink non-generated collections or user data.
    pending = set(owned_collections)
    while pending:
        leaves = [collection for collection in pending if not any(child in pending for child in collection.children)]
        for collection in leaves:
            pending.remove(collection)
            if not collection.objects and not collection.children:
                bpy.data.collections.remove(collection, do_unlink=True)


def make_collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    collection["intermedia_owned"] = True
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
    size = 192
    image = bpy.data.images.new(name, width=size, height=size, alpha=False)
    pixels: list[float] = []
    for y in range(size):
        for x in range(size):
            if kind == "brick":
                row = y // 24
                offset = 24 if row % 2 else 0
                mortar = (y % 24 < 2) or ((x + offset) % 48 < 2)
                value = 0.62 if mortar else 0.90 + ((x * 17 + y * 7) % 9) / 100.0
                rgb = (value, value, value)
            elif kind == "wood":
                grain = 0.04 * math.sin(x * math.pi / 8 + 0.7 * math.sin(y * math.tau / size))
                value = 0.66 if x % 48 < 2 else 0.92 + grain
                rgb = (value, value, value)
            elif kind == "asphalt":
                value = 0.88 + ((x * 13 + y * 19) % 17) / 160.0
                rgb = (value, value, value)
            elif kind == "tile":
                grout = (x % 48 < 1) or (y % 48 < 1)
                rgb = (0.60, 0.60, 0.60) if grout else (0.96, 0.96, 0.96)
            else:
                value = 0.84 + ((x * 5 + y * 11) % 15) / 100.0
                rgb = (value, value, value)
            pixels.extend((*rgb, 1.0))
    image.pixels = pixels
    image.pack()
    return image


def make_normal_image(name: str, height_image: bpy.types.Image, kind: str) -> bpy.types.Image:
    """Finite differences of a periodic height field, in physical metres."""
    width, height = height_image.size
    pixels = list(height_image.pixels[:])
    heights = pixels[::4]
    repeat_x, repeat_y = TEXTURE_METERS[kind]
    relief = {"brick": 0.006, "wood": 0.001, "tile": 0.003, "asphalt": 0.001}[kind]
    normals = []
    for y in range(height):
        for x in range(width):
            dx = (heights[y * width + (x + 1) % width] - heights[y * width + (x - 1) % width]) * relief * width / (2 * repeat_x)
            dy = (heights[((y + 1) % height) * width + x] - heights[((y - 1) % height) * width + x]) * relief * height / (2 * repeat_y)
            normal = Vector((-dx, -dy, 1.0)).normalized()
            normals.extend((normal.x * 0.5 + 0.5, normal.y * 0.5 + 0.5, normal.z * 0.5 + 0.5, 1.0))
    image = bpy.data.images.new(name, width=width, height=height, alpha=False)
    image.colorspace_settings.name = "Non-Color"
    image.pixels = normals
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
    # Palette values are artist-facing sRGB, whereas Principled Base Color and
    # generated image pixels are linear. Treating them as linear bleaches dark
    # plaster and turns natural foliage pastel under daylight.
    if texture_kind is None:
        color = tuple(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in color)
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
        if texture_kind in ("brick", "wood", "tile", "asphalt"):
            normal_tex = nodes.new("ShaderNodeTexImage")
            normal_tex.image = make_normal_image(f"IMG-{name}-Normal", image, texture_kind)
            normal_tex.extension = "REPEAT"
            normal_tex.interpolation = "Linear"
            normal_map = nodes.new("ShaderNodeNormalMap")
            normal_map.space = "TANGENT"
            normal_map.uv_map = "UVMap"
            links.new(normal_tex.outputs["Color"], normal_map.inputs["Color"])
            links.new(normal_map.outputs["Normal"], shader.inputs["Normal"])
        # Bake the tint into the image: direct image-to-base-color exports to
        # glTF reliably and keeps related materials from becoming identical.
        pixels = list(image.pixels[:])
        for index in range(0, len(pixels), 4):
            for channel in range(3):
                pixels[index + channel] *= color[channel]
        image.pixels = pixels
        image.pack()
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
    repeat_x, repeat_y = TEXTURE_METERS.get(mat.get("texture_kind") if mat else None, (1.0, 1.0))
    for polygon in mesh.polygons:
        normal = polygon.normal
        for loop_index in polygon.loop_indices:
            coordinate = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            if abs(normal.z) > 0.5:
                uv = (coordinate.x / repeat_x, coordinate.y / repeat_y)
            elif abs(normal.y) > 0.5:
                uv = (coordinate.x / repeat_x, coordinate.z / repeat_y)
            else:
                uv = (coordinate.y / repeat_x, coordinate.z / repeat_y)
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
    for polygon in obj.data.polygons[2:]:
        polygon.use_smooth = True
    return obj


def sphere(name: str, location: tuple[float, float, float], scale: tuple[float, float, float], collection: bpy.types.Collection, parent: bpy.types.Object | None, mat: bpy.types.Material, role: str) -> bpy.types.Object:
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.0)
    obj = bpy.context.object
    obj.name = name
    for linked in list(obj.users_collection):
        linked.objects.unlink(obj)
    collection.objects.link(obj)
    if parent:
        obj.parent = parent
    obj.location = location
    obj.scale = scale
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    assign_material(obj, mat)
    return mark(obj, role)


def wall_between_openings(prefix: str, total_width: float, height: float, thickness: float, openings: list[tuple[float, float, float, float]], axis: str, fixed: float, collection: bpy.types.Collection, parent: bpy.types.Object, mat: bpy.types.Material, role: str = "exterior_wall", regions: tuple = ()) -> None:
    """Tile one wall volume around (center, width, sill, head) voids.

    Color regions replace wall cells; they never add a coplanar skin. The grid
    includes sill/head edges, so openings have real lintels and closed reveals.
    """
    holes = [(center - width / 2, center + width / 2, bottom, top) for center, width, bottom, top in openings]
    rectangles = holes + [region[:4] for region in regions]
    xs = sorted({-total_width / 2, total_width / 2} | {max(-total_width / 2, min(total_width / 2, value)) for rect in rectangles for value in rect[:2]})
    zs = sorted({0.0, height} | {max(0.0, min(height, value)) for rect in rectangles for value in rect[2:4]})
    cells = {}
    for xi, (lo, hi) in enumerate(zip(xs, xs[1:])):
        for zi, (bottom, top) in enumerate(zip(zs, zs[1:])):
            u, z = (lo + hi) / 2, (bottom + top) / 2
            if any(left < u < right and sill < z < head for left, right, sill, head in holes):
                continue
            cell_mat = mat
            for left, right, sill, head, region_mat in regions:
                if left < u < right and sill < z < head:
                    cell_mat = region_mat
            cells[(xi, zi)] = cell_mat
    batches = {}
    for (xi, zi), cell_mat in cells.items():
        lo, hi, bottom, top = xs[xi], xs[xi + 1], zs[zi], zs[zi + 1]
        x0, x1, y0, y1 = (lo, hi, fixed - thickness / 2, fixed + thickness / 2) if axis == "x" else (fixed - thickness / 2, fixed + thickness / 2, lo, hi)
        vertices, faces, volumes = batches.setdefault(cell_mat, ([], [], []))
        volumes.append([x0, x1, y0, y1, bottom, top])
        offset = len(vertices)
        vertices.extend([(x0, y0, bottom), (x1, y0, bottom), (x1, y1, bottom), (x0, y1, bottom), (x0, y0, top), (x1, y0, top), (x1, y1, top), (x0, y1, top)])
        neighbors = [(xi, zi - 1), (xi, zi + 1), None, (xi + 1, zi), None, (xi - 1, zi)] if axis == "x" else [(xi, zi - 1), (xi, zi + 1), (xi - 1, zi), None, (xi + 1, zi), None]
        for face, neighbor in zip(((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)), neighbors):
            if neighbor not in cells:
                faces.append(tuple(offset + index for index in face))
    for index, (cell_mat, (vertices, faces, volumes)) in enumerate(batches.items()):
        wall = mesh_object(f"{prefix}_Material_{index}", vertices, faces, collection, parent, cell_mat, role)
        # The viewer caps these original solids independently. Taking a convex
        # hull over an entire windowed wall would incorrectly fill its openings.
        wall["section_cells_json"] = json.dumps(volumes)


def join_tree_parts(name: str, parts: list[bpy.types.Object], collection: bpy.types.Collection, tree: bpy.types.Object, role: str) -> None:
    """Bake tree-local transforms into one mesh; retain material slots/shading."""
    vertices, faces, face_materials, smooth, materials = [], [], [], [], []
    for part in parts:
        transform = Matrix.LocRotScale(part.location, part.rotation_euler.to_quaternion(), part.scale)
        offset = len(vertices)
        vertices.extend(tuple(transform @ vertex.co) for vertex in part.data.vertices)
        for polygon in part.data.polygons:
            mat = part.data.materials[polygon.material_index]
            if mat not in materials:
                materials.append(mat)
            faces.append(tuple(offset + index for index in polygon.vertices))
            face_materials.append(materials.index(mat))
            smooth.append(polygon.use_smooth)
    merged = mesh_object(name, vertices, faces, collection, tree, None, role)
    for mat in materials:
        merged.data.materials.append(mat)
    for polygon, mat_index, use_smooth in zip(merged.data.polygons, face_materials, smooth):
        polygon.material_index = mat_index
        polygon.use_smooth = use_smooth
    for part in parts:
        mesh = part.data
        bpy.data.objects.remove(part, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def add_hollow_trim(prefix: str, x: float, z: float, width: float, height: float, collection: bpy.types.Collection, parent: bpy.types.Object) -> None:
    border = 0.18
    for side in (-1, 1):
        box(f"{prefix}_Jamb_{side}", (x + side * (width + border) / 2, -0.18, z), (border, 0.08, height), collection, parent, MATS["trim"], "facade_trim", 0.012)
        box(f"{prefix}_Rail_{side}", (x, -0.18, z + side * (height + border) / 2), (width + 2 * border, 0.08, border), collection, parent, MATS["trim"], "facade_trim", 0.012)


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
    box(f"{prefix}_Curtain", (x + width * 0.36, y + 0.20, z), (width * 0.16, 0.025, height * 0.86), collection, parent, MATS["curtain"], "window_curtain")


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
    floor_index = int(floor["floor_index"])
    box(f"{floor_id}_ArrivalLanding", (0.0, -2.5, (FINISH_BOTTOM + FINISH_TOP) / 2), (3.3, 0.8, FINISH_TOP - FINISH_BOTTOM), collection, core, MATS["tile"], "stair_landing")
    for side in (-1, 1):
        box(f"{floor_id}_StairWall_{side}", (side * 1.8, 0.0, 1.35), (0.18, 4.8, 2.7), collection, core, MATS["concrete"], "stairwell_wall", 0.02)
    # Top floor has the arrival opening but no flight into the roof.
    if floor_index == len(FLOOR_HEIGHTS) - 1:
        return
    height = FLOOR_HEIGHTS[floor_index]
    count = math.ceil(height / (2 * 0.19))
    rise, going, start = height / (2 * count), 0.30, -2.1
    far = start + count * going
    for flight in range(2):
        x = -0.85 if flight == 0 else 0.85
        for step in range(count):
            y = start + (step + 0.5) * going if flight == 0 else far - (step + 0.5) * going
            top = FINISH_TOP + (flight * count + step + 1) * rise
            box(f"{floor_id}_Flight_{flight}_Tread_{step:02d}", (x, y, top - 0.035), (1.5, going, 0.07), collection, core, MATS["wood"], "stair_tread", 0.008)
            riser_y = y - going / 2 if flight == 0 else y + going / 2
            box(f"{floor_id}_Flight_{flight}_Riser_{step:02d}", (x, riser_y, top - rise / 2), (1.5, 0.025, rise), collection, core, MATS["concrete"], "stair_riser")
            if step % 3 == 0 or step == count - 1:
                cylinder(f"{floor_id}_RailPost_{flight}_{step}", (x * 0.15, y, top + 0.45), 0.025, 0.9, collection, core, MATS["frame"], 12, role="stair_handrail_post")
        rail_start = Vector((x * 0.15, start + going / 2, FINISH_TOP + (rise if flight == 0 else height) + 0.9))
        rail_end = Vector((x * 0.15, far - going / 2, FINISH_TOP + (height / 2 if flight == 0 else height / 2 + rise) + 0.9))
        rail = cylinder(f"{floor_id}_Handrail_{flight}", tuple((rail_start + rail_end) / 2), 0.035, (rail_end - rail_start).length, collection, core, MATS["frame"], 12, role="stair_handrail")
        rail.rotation_euler = (rail_end - rail_start).to_track_quat("Z", "Y").to_euler()
    box(f"{floor_id}_MidLanding", (0.0, far + 0.5, FINISH_TOP + height / 2 - 0.06), (3.2, 1.0, 0.12), collection, core, MATS["concrete"], "stair_landing")


def add_floor_plate(prefix: str, z: float, thickness: float, width: float, depth: float, collection: bpy.types.Collection, parent: bpy.types.Object, mat: bpy.types.Material, role: str, stair_void: bool, **metadata: object) -> None:
    """Disjoint plate rectangles leave a 3.3 × 4.5 m stair opening."""
    rectangles = [(0.0, 0.0, width, depth)]
    if stair_void:
        side_width = width / 2 - 1.65
        rectangles = [(-1.65 - side_width / 2, 0.0, side_width, depth), (1.65 + side_width / 2, 0.0, side_width, depth)]
        for low, high in ((-depth / 2, -1.3), (3.2, depth / 2)):
            rectangles.append((0.0, (low + high) / 2, 3.3, high - low))
    for index, (x, y, dx, dy) in enumerate(rectangles):
        box(f"{prefix}_{index}", (x, y, z), (dx, dy, thickness), collection, parent, mat, role, 0.008, **metadata)


def add_generic_layout(floor: bpy.types.Object, collection: bpy.types.Collection, block_id: str, floor_index: int) -> None:
    floor_id = f"BLK-{block_id}_F{floor_index}"
    add_stair_core(floor, collection, floor_id)
    for side, x in (("L", -8.8), ("R", 8.8)):
        if side == "L" and (block_id, floor_index) in DETAILED_FLOORS:
            continue
        unit = empty(f"{floor_id}_UNIT_{side}", collection, floor, (x, 0.8, 0.0), "apartment_shell", building_id=block_id, floor_id=floor_id, unit_kind="representative", furnished=True, furniture_level="illustrative")
        box(f"{floor_id}_UnitFloor_{side}", (0.0, 0.0, (FINISH_BOTTOM + FINISH_TOP) / 2), (8.0, 10.2, FINISH_TOP - FINISH_BOTTOM), collection, unit, MATS["wood_floor"], "apartment_floor", floor_id=floor_id)
        box(f"{floor_id}_UnitPartition_{side}", (0.0, 0.9, 1.45), (0.12, 6.2, 2.7), collection, unit, MATS["white"], "interior_partition", 0.02, floor_id=floor_id)
        box(f"{floor_id}_UnitBackWall_{side}", (0.0, 5.0, 1.45), (8.0, 0.14, 2.7), collection, unit, MATS["white"], "interior_partition", 0.02, floor_id=floor_id)
        box(f"{floor_id}_UnitEntry_{side}", (0.0, -4.95, 1.1), (1.1, 0.10, 2.2), collection, unit, MATS["wood_dark"], "interior_door")
        add_generic_furniture(f"{floor_id}_{side}", collection, unit, floor_index)


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


def add_generic_furniture(prefix: str, collection: bpy.types.Collection, parent: bpy.types.Object, floor_index: int) -> None:
    """Give every illustrative apartment a compact, non-hero furniture pass."""
    add_kitchen(f"{prefix}_Kitchen", (0.0, 4.15), collection, parent, 3.4)
    add_sofa(f"{prefix}_Sofa", (-1.85, -1.55), collection, parent)
    add_table(f"{prefix}_Dining", (1.15, -1.55), collection, parent)
    add_bed(f"{prefix}_Bed", (2.05, 2.55), collection, parent, 1.5)
    add_bathroom(f"{prefix}_Bath", (-2.8, 2.75), collection, parent, 1.65, 2.1)
    add_rug(f"{prefix}_Rug", (-1.35, -1.55), (2.45, 1.75), collection, parent)
    add_plant(f"{prefix}_Plant", (-3.35, -1.35), collection, parent, 0.58 + floor_index * 0.025)


def add_bathroom(prefix: str, location: tuple[float, float], collection: bpy.types.Collection, parent: bpy.types.Object, width: float, depth: float) -> None:
    x, y = location
    box(f"{prefix}_Floor", (x, y, FINISH_TOP + 0.015), (width, depth, 0.02), collection, parent, MATS["tile"], "bathroom_floor")
    box(f"{prefix}_BackTile", (x, y + depth / 2.0, 1.45), (width, 0.10, 2.7), collection, parent, MATS["tile_speckle"], "bathroom_tile")
    box(f"{prefix}_SideTile", (x - width / 2.0, y, 1.45), (0.10, depth, 2.7), collection, parent, MATS["tile"], "bathroom_tile")
    box(f"{prefix}_Vanity", (x - 0.35, y + 0.45, 0.78), (0.95, 0.48, 0.68), collection, parent, MATS["white"], "bathroom_vanity", 0.04)
    box(f"{prefix}_Sink", (x - 0.35, y + 0.19, 1.18), (0.62, 0.34, 0.10), collection, parent, MATS["ceramic"], "bathroom_sink", 0.03)
    box(f"{prefix}_Mirror", (x - 0.35, y + 0.13, 2.0), (0.78, 0.05, 0.78), collection, parent, MATS["mirror"], "bathroom_mirror")
    box(f"{prefix}_Toilet", (x + 0.62, y + 0.3, 0.52), (0.66, 0.98, 0.58), collection, parent, MATS["ceramic"], "toilet", 0.12)
    box(f"{prefix}_ShowerGlass", (x + 0.62, y - 0.65, 1.32), (0.05, 1.2, 2.35), collection, parent, MATS["glass"], "shower_glass")
    cylinder(f"{prefix}_ShowerHead", (x + 0.62, y - 0.85, 2.15), 0.12, 0.05, collection, parent, MATS["frame"], 16, rotation=(math.radians(90), 0.0, 0.0), role="shower_fitting")


def add_rug(prefix: str, location: tuple[float, float], size: tuple[float, float], collection: bpy.types.Collection, parent: bpy.types.Object) -> None:
    box(prefix, (location[0], location[1], FINISH_TOP + 0.018), (size[0], size[1], 0.025), collection, parent, MATS["rug"], "rug", 0.005)


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
    box(f"{prefix}_Floor", (0.0, 0.0, (FINISH_BOTTOM + FINISH_TOP) / 2), (width, depth, FINISH_TOP - FINISH_BOTTOM), collection, unit, MATS["wood_floor"], "apartment_floor", floor_id=floor_id, usable_area=usable_area)
    for side, x in (("L", -width / 2.0), ("R", width / 2.0)):
        box(f"{prefix}_Wall_{side}", (x, 0.0, 1.45), (0.12, depth, 2.75), collection, unit, MATS["white"], "interior_partition", 0.02)
    box(f"{prefix}_Wall_Back", (0.0, depth / 2.0, 1.45), (width, 0.12, 2.75), collection, unit, MATS["white"], "interior_partition", 0.02)
    # Match the long balcony rhythm visible on the reference elevations. Keep
    # the supplied 6.60 m² area by making these balconies broad and shallow;
    # their back edge remains aligned to the apartment's front opening.
    balcony_width = 5.0
    balcony_depth = balcony_area / balcony_width
    # This is the apartment's actual exterior balcony, replacing the generic
    # left balcony on this floor; no miniature balcony inside the footprint.
    balcony = empty(f"{prefix}_BALCONY", collection, unit, (0.0, -depth / 2.0 - balcony_depth / 2.0 - 0.20, 0.0), "balcony", balcony_area=balcony_area, explosion_group="balcony")
    box(f"{prefix}_BalconySlab", (0.0, 0.0, 0.15), (balcony_width, balcony_depth, 0.25), collection, balcony, MATS["concrete"], "balcony_slab", 0.04)
    box(f"{prefix}_BalconyParapet", (0.0, -balcony_depth / 2.0, 0.95), (balcony_width, 0.16, 1.35), collection, balcony, MATS["brick"], "balcony_parapet", 0.03)
    box(f"{prefix}_BalconyCoping", (0.0, -balcony_depth / 2.0, 1.67), (balcony_width + 0.12, 0.22, 0.12), collection, balcony, MATS["concrete"], "balcony_coping", 0.025)
    for side in (-1, 1):
        box(f"{prefix}_BalconySideReturn_{side}", (side * (balcony_width / 2.0 - 0.08), 0.0, 1.0), (0.16, balcony_depth, 1.45), collection, balcony, MATS["frame"], "balcony_rail", 0.02)
    box(f"{prefix}_BalconyDoorGlass", (0.0, balcony_depth / 2.0 - 0.06, 1.16), (1.50, 0.06, 2.12), collection, balcony, MATS["glass"], "balcony_door_glazing", 0.02)
    box(f"{prefix}_BalconyThreshold", (0.0, balcony_depth / 2.0 - 0.12, 0.31), (1.62, 0.14, 0.08), collection, balcony, MATS["frame"], "balcony_threshold", 0.015)
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
        # Keep every representative balcony on the same left façade bay so
        # the parapet, glazing and opening read as one aligned assembly.
        unit.location.x = -10.0
        unit.location.y = -BUILDING_DEPTH / 2 + depth / 2
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
        add_floor_plate(f"{floor_id}_Slab", -SLAB_THICKNESS / 2, SLAB_THICKNESS, BUILDING_WIDTH, BUILDING_DEPTH, floor_collection, floor, MATS["concrete"], "floor_slab", floor_index > 0, building_id=block_id, floor_id=floor_id, explosion_group="structure")
        ceiling_top = floor_height - SLAB_THICKNESS - 0.02
        add_floor_plate(f"{floor_id}_Ceiling", ceiling_top - 0.025, 0.05, BUILDING_WIDTH - 0.1, BUILDING_DEPTH - 0.1, floor_collection, floor, MATS["ceiling"], "ceiling", floor_index < 3, building_id=block_id, floor_id=floor_id, section_removable=True, explosion_group="ceiling")
        facade = empty(f"{floor_id}_FACADE_FRONT", floor_collection, floor, (0.0, -BUILDING_DEPTH / 2.0 - 0.08, 0.0), "facade", building_id=block_id, floor_id=floor_id, facade_side="front", explosion_group="facade")
        back = empty(f"{floor_id}_FACADE_BACK", floor_collection, floor, (0.0, BUILDING_DEPTH / 2.0 + 0.08, 0.0), "facade", building_id=block_id, floor_id=floor_id, facade_side="back", explosion_group="facade")
        left = empty(f"{floor_id}_FACADE_LEFT", floor_collection, floor, (-BUILDING_WIDTH / 2.0 - 0.08, 0.0, 0.0), "facade", building_id=block_id, floor_id=floor_id, facade_side="left", explosion_group="facade")
        right = empty(f"{floor_id}_FACADE_RIGHT", floor_collection, floor, (BUILDING_WIDTH / 2.0 + 0.08, 0.0, 0.0), "facade", building_id=block_id, floor_id=floor_id, facade_side="right", explosion_group="facade")
        back.rotation_euler.z = math.pi
        left.rotation_euler.z = math.pi
        if floor_index == 0:
            openings = [(-11.0, 3.0), (-7.0, 3.0), (-3.6, 3.1), (3.6, 3.1), (7.0, 3.0), (11.0, 3.0)]
            win_z, win_h = 1.78, 2.25
        else:
            openings = [(-11.3, 3.0), (-7.0, 2.6), (-3.3, 2.1), (3.3, 2.1), (7.0, 2.6), (11.3, 3.0)]
            win_z, win_h = floor_height / 2.0 + 0.25, 1.55
        sill, head = win_z - win_h / 2 - 0.05, win_z + win_h / 2 + 0.05
        front_holes = [(x, width, sill, head) for x, width in openings]
        if floor_index == 0:
            front_holes.append((0.0, 2.8, 0.0, 2.70))
        regions = ((-14.0, 14.0, 0.0, 2.2, MATS["charcoal"]),) if floor_index == 0 else ((-6.3, 6.3, 0.0, floor_height, MATS["graphite"]),)
        wall_between_openings(f"{floor_id}_FrontWall", BUILDING_WIDTH, floor_height, 0.24, front_holes, "x", 0.0, floor_collection, facade, MATS["white"], regions=regions)
        for index, (x, width) in enumerate(openings):
            add_front_window(f"{floor_id}_FrontWindow_{index}", x, win_z, width - 0.07, win_h, floor_collection, facade, floor_id)
        back_openings = [(-10.8, 2.6), (-6.0, 2.6), (6.0, 2.6), (10.8, 2.6)]
        wall_between_openings(f"{floor_id}_BackWall", BUILDING_WIDTH, floor_height, 0.24, [(x, width, sill, head) for x, width in back_openings], "x", 0.0, floor_collection, back, MATS["white"])
        for index, (x, width) in enumerate(back_openings):
            add_front_window(f"{floor_id}_BackWindow_{index}", x, win_z, width - 0.07, win_h, floor_collection, back, floor_id)
        side_openings = [(-4.5, 2.2), (0.0, 2.2), (4.5, 2.2)]
        side_holes = [(y, width, sill, head) for y, width in side_openings]
        side_regions = ((-BUILDING_DEPTH / 2, BUILDING_DEPTH / 2, sill - 0.16, head + 0.16, MATS["graphite"]),)
        wall_between_openings(f"{floor_id}_LeftWall", BUILDING_DEPTH, floor_height, 0.24, side_holes, "y", 0.0, floor_collection, left, MATS["white"], regions=side_regions)
        wall_between_openings(f"{floor_id}_RightWall", BUILDING_DEPTH, floor_height, 0.24, side_holes, "y", 0.0, floor_collection, right, MATS["white"], regions=side_regions)
        for index, (y, width) in enumerate(side_openings):
            add_side_window(f"{floor_id}_SideL_{index}", y, win_z, width - 0.07, win_h, 0.0, floor_collection, left, floor_id)
            add_side_window(f"{floor_id}_SideR_{index}", y, win_z, width - 0.07, win_h, 0.0, floor_collection, right, floor_id)
        if floor_index > 0:
            for x in (-3.3, 3.3):
                add_hollow_trim(f"{floor_id}_WhiteTrim_{x}", x, win_z, 2.1, head - sill, floor_collection, facade)
        if floor_index > 0:
            if (block_id, floor_index) not in DETAILED_FLOORS:
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
    # Downpipes sit outside the balcony line at the building corners. Keeping
    # them beyond the parapet envelope prevents a vertical service element
    # from visually piercing a terrace.
    for x in (-14.35, 14.35):
        box(f"BLK-{block_id}_Downpipe_{x}", (x, -6.72, -7.0), (0.12, 0.12, 14.0), roof_collection, roof, MATS["frame"], "roof_downpipe")
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
    car = empty(prefix, collection, parent, (x, y, COURT_TOP), "vehicle", vehicle_class="compact", length_m=4.2, width_m=2.08)
    # All component coordinates are car-local; rotate the assembly once.
    car.rotation_euler.z = rotation
    box(f"{prefix}_Body", (0.0, 0.0, 0.59), (4.1, 1.75, 0.54), collection, car, body_mat, "vehicle_body", 0.12)
    cabin_vertices = [(-1.05, -0.73, 0.86), (1.35, -0.73, 0.86), (1.35, 0.73, 0.86), (-1.05, 0.73, 0.86), (-0.55, -0.62, 1.42), (0.9, -0.62, 1.42), (0.9, 0.62, 1.42), (-0.55, 0.62, 1.42)]
    mesh_object(f"{prefix}_Cabin", cabin_vertices, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], collection, car, MATS["car_glass"], "vehicle_glazing", 0.025)
    box(f"{prefix}_Roof", (0.175, 0.0, 1.455), (1.5, 1.3, 0.06), collection, car, body_mat, "vehicle_roof", 0.025)
    box(f"{prefix}_Hood", (-1.52, 0.0, 0.89), (0.95, 1.60, 0.08), collection, car, body_mat, "vehicle_body", 0.035)
    for side in (-1, 1):
        box(f"{prefix}_Pillar_{side}", (0.3, side * 0.695, 1.13), (0.10, 0.06, 0.56), collection, car, body_mat, "vehicle_pillar", 0.01, rotation=(side * 0.194, 0.0, 0.0))
        box(f"{prefix}_Mirror_{side}", (-0.8, side * 0.96, 0.99), (0.24, 0.16, 0.14), collection, car, body_mat, "vehicle_mirror", 0.045)
        for door_x in (-0.45, 0.9):
            box(f"{prefix}_Handle_{side}_{door_x}", (door_x, side * 0.88, 0.76), (0.16, 0.025, 0.035), collection, car, MATS["alloy"], "vehicle_handle", 0.01)
        box(f"{prefix}_Sill_{side}", (0.0, side * 0.88, 0.35), (2.0, 0.035, 0.08), collection, car, MATS["rubber"], "vehicle_sill", 0.02)
    for index, (dx, dy) in enumerate(((-1.3, -0.88), (-1.3, 0.88), (1.3, -0.88), (1.3, 0.88))):
        cylinder(f"{prefix}_Wheel_{index}", (dx, dy, 0.34), 0.34, 0.18, collection, car, MATS["rubber"], 32, rotation=(math.pi / 2.0, 0.0, 0.0), role="vehicle_wheel")
        outer_y = dy + math.copysign(0.095, dy)
        cylinder(f"{prefix}_Rim_{index}", (dx, outer_y, 0.34), 0.22, 0.025, collection, car, MATS["alloy"], 32, rotation=(math.pi / 2, 0.0, 0.0), role="vehicle_rim")
        cylinder(f"{prefix}_Hub_{index}", (dx, outer_y + math.copysign(0.02, dy), 0.34), 0.075, 0.025, collection, car, MATS["frame"], 16, rotation=(math.pi / 2, 0.0, 0.0), role="vehicle_hub")
    for index, dy in enumerate((-0.54, 0.54)):
        box(f"{prefix}_Headlight_{index}", (-2.06, dy, 0.69), (0.06, 0.32, 0.16), collection, car, MATS["headlight"], "vehicle_light", 0.02)
        box(f"{prefix}_Taillight_{index}", (2.06, dy, 0.69), (0.06, 0.30, 0.15), collection, car, MATS["taillight"], "vehicle_light", 0.02)
    for end in (-1, 1):
        box(f"{prefix}_Bumper_{end}", (end * 2.06, 0.0, 0.44), (0.08, 1.35, 0.10), collection, car, MATS["rubber"], "vehicle_bumper", 0.025)
        box(f"{prefix}_Plate_{end}", (end * 2.085, 0.0, 0.65), (0.02, 0.40, 0.12), collection, car, MATS["road_line"], "vehicle_plate", 0.01)


def add_tree(prefix: str, location: tuple[float, float], scale: float, collection: bpy.types.Collection, parent: bpy.types.Object) -> None:
    x, y = location
    tree = empty(prefix, collection, parent, (x, y, 0.0), "landscape_tree")
    tree["asset_detail"] = "smooth irregular crown, branches and leaf sprays"
    cylinder(f"{prefix}_Trunk", (0.0, 0.0, 1.8 * scale), 0.18 * scale, 3.6 * scale, collection, tree, MATS["trunk"], 20, role="tree_trunk")
    phase = sum(map(ord, prefix)) * 0.31
    leaf_vertices, leaf_faces = [], []
    for index in range(18):
        angle = phase + index * 2.399963
        radial = 0.65 + 0.65 * math.sin(index * 1.7) ** 2
        center = Vector((math.cos(angle) * radial, math.sin(angle) * radial, 3.2 + (index % 6) * 0.38)) * scale
        start = Vector((0.0, 0.0, (2.0 + (index % 4) * 0.25) * scale))
        branch = cylinder(f"{prefix}_Branch_{index}", tuple((start + center) / 2), 0.055 * scale, (center - start).length, collection, tree, MATS["trunk"], 10, role="tree_branch")
        branch.rotation_euler = (center - start).to_track_quat("Z", "Y").to_euler()
        for sprig in range(180):
            a = angle + sprig * 2.4
            v = ((sprig * 0.41421356 + index * 0.23) % 1) * 2 - 1
            radius = (0.1 + 0.9 * ((sprig * 0.754877 + index * 0.37) % 1)) ** (1 / 3)
            spread = math.sqrt(1 - v * v)
            pos = center + Vector((math.cos(a) * spread * 0.88, math.sin(a) * spread * 0.78, v * 0.95)) * radius * scale
            along = Vector((math.cos(a), math.sin(a), 0.5 * math.sin(sprig))) * (0.10 * scale)
            across = Vector((-math.sin(a), math.cos(a), 0.25 * math.cos(sprig))) * (0.045 * scale)
            ridge = Vector((0.0, 0.0, 0.012 * scale))
            offset = len(leaf_vertices)
            leaf_vertices.extend(tuple(point) for point in (pos - along, pos + across, pos + along, pos - across, pos + ridge, pos - ridge))
            leaf_faces.extend(tuple(offset + v for v in face) for face in ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (1, 0, 5), (2, 1, 5), (3, 2, 5), (0, 3, 5)))
    leaf_mesh = mesh_object(f"{prefix}_LeafSprays", leaf_vertices, leaf_faces, collection, tree, MATS["leaf"], "tree_leaves")
    leaf_mesh.data.materials.append(MATS["leaf_dark"])
    leaf_mesh.data.materials.append(MATS["leaf_light"])
    for polygon in leaf_mesh.data.polygons:
        polygon.material_index = (polygon.index // 8) % 3
    parts = list(tree.children)
    wood = [obj for obj in parts if obj.get("role") in ("tree_trunk", "tree_branch")]
    foliage = [obj for obj in parts if obj.get("role") in ("tree_canopy", "tree_leaves")]
    join_tree_parts(f"{prefix}_Wood", wood, collection, tree, "tree_trunk")
    join_tree_parts(f"{prefix}_Foliage", foliage, collection, tree, "tree_canopy")


def add_banner_text(prefix: str, body: str, location: tuple[float, float, float], size: float, collection: bpy.types.Collection, parent: bpy.types.Object, material: bpy.types.Material) -> None:
    """Create shallow, real 3D lettering for a site marketing banner."""
    curve = bpy.data.curves.new(f"{prefix}_TextCurve", type="FONT")
    curve.body = body
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = 0.018
    curve.bevel_depth = 0.004
    curve.materials.append(material)
    text = bpy.data.objects.new(prefix, curve)
    collection.objects.link(text)
    text.parent = parent
    text.location = location
    text.rotation_euler.x = math.pi / 2.0
    mark(text, "marketing_banner_text", marketing_copy=body, banner_id=parent.name)
    bpy.ops.object.select_all(action="DESELECT")
    text.select_set(True)
    bpy.context.view_layer.objects.active = text
    bpy.ops.object.convert(target="MESH")
    text.select_set(False)


def add_marketing_banner(prefix: str, location: tuple[float, float], scale: float, collection: bpy.types.Collection, parent: bpy.types.Object) -> None:
    """Add a dimensional INTERMEDIA sign that lives in the parking context."""
    x, y = location
    banner = empty(prefix, collection, parent, (x, y, 0.0), "marketing_banner", marketing_copy="INTERMEDIA · Alege-ți locul")
    width, height = 5.2 * scale, 1.8 * scale
    box(f"{prefix}_Panel", (0.0, 0.0, 1.42 * scale), (width, 0.16 * scale, height), collection, banner, MATS["blue"], "marketing_banner_panel", 0.05 * scale)
    for side in (-1, 1):
        box(f"{prefix}_FrameV_{side}", (side * width / 2.0, -0.10 * scale, 1.42 * scale), (0.09 * scale, 0.08 * scale, height + 0.14 * scale), collection, banner, MATS["gold"], "marketing_banner_frame", 0.02 * scale)
    for z in (1.42 * scale - height / 2.0, 1.42 * scale + height / 2.0):
        box(f"{prefix}_FrameH_{z}", (0.0, -0.10 * scale, z), (width + 0.18 * scale, 0.08 * scale, 0.09 * scale), collection, banner, MATS["gold"], "marketing_banner_frame", 0.02 * scale)
    for side in (-1, 1):
        box(f"{prefix}_Post_{side}", (side * (width / 2.0 - 0.25 * scale), 0.0, 0.50 * scale), (0.12 * scale, 0.12 * scale, 1.0 * scale), collection, banner, MATS["frame"], "marketing_banner_post")
        box(f"{prefix}_Foot_{side}", (side * (width / 2.0 - 0.25 * scale), 0.0, 0.06 * scale), (0.52 * scale, 0.38 * scale, 0.12 * scale), collection, banner, MATS["concrete"], "marketing_banner_foot", 0.03 * scale)
    add_banner_text(f"{prefix}_Brand", "INTERMEDIA", (0.0, -0.115 * scale, 1.68 * scale), 0.47 * scale, collection, banner, MATS["gold"])
    add_banner_text(f"{prefix}_Message", "ALEGE-ȚI LOCUL", (0.0, -0.115 * scale, 1.15 * scale), 0.23 * scale, collection, banner, MATS["white"])


def add_site(root_collection: bpy.types.Collection) -> None:
    site_collection = make_collection("Site_Context", root_collection)
    site = empty("SITE", site_collection, ROOT, (0.0, 0.0, 0.0), "site")
    box("SITE_ContextGround", (0.0, 14.0, -0.70), (500.0, 500.0, 1.2), site_collection, site, MATS["grass"], "landscape_context")
    box("SITE_Terrain", (0.0, 14.0, -0.34), (120.0, 104.0, 0.55), site_collection, site, MATS["grass"], "site_ground", 0.25)
    # One pavement surface with holes for building foundations. No raised lane
    # overlays, and no asphalt passing through ground-floor finishes.
    xs = (-31.0, -14.22, 14.22, 31.0)
    ys = sorted({-30.0, 54.0} | {center + side * 6.72 for center in BUILDINGS.values() for side in (-1, 1)})
    for xi, (left, right) in enumerate(zip(xs, xs[1:])):
        for yi, (front, back) in enumerate(zip(ys, ys[1:])):
            x, y = (left + right) / 2, (front + back) / 2
            if abs(x) < 14.22 and any(abs(y - center) < 6.72 for center in BUILDINGS.values()):
                continue
            box(f"SITE_Court_{xi}_{yi}", (x, y, COURT_TOP - 0.09), (right - left, back - front, 0.18), site_collection, site, MATS["asphalt"], "access_court")
    box("SITE_Street", (0.0, -35.0, 0.0), (120.0, 5.2, 0.20), site_collection, site, MATS["asphalt"], "public_street")
    box("SITE_Sidewalk", (0.0, -31.8, 0.12), (120.0, 1.8, 0.16), site_collection, site, MATS["paving"], "sidewalk")
    # (centre x, centre y, heading). The local X axis is the five-metre
    # vehicle/bay length; local Y is its 2.5-metre width.
    bays = [(x, -24.0, math.pi / 2) for x in (-21.25 + i * BAY_WIDTH for i in range(18))]
    bays += [(side * 24.0, -12.5 + i * BAY_WIDTH, 0.0 if side < 0 else math.pi) for side in (-1, 1) for i in range(25)]
    colors = [MATS["car_red"], MATS["car_white"], MATS["car_blue"], MATS["car_yellow"], MATS["car_silver"], MATS["car_dark"]]
    marking_z = COURT_TOP + 0.012
    for index, (x, y, heading) in enumerate(bays):
        bay_id = f"PARKING_{index:03d}"
        bay = empty(bay_id, site_collection, site, (x, y, 0.0), "parking_bay", bay_id=bay_id, width_m=BAY_WIDTH, length_m=BAY_LENGTH)
        bay.rotation_euler.z = heading
        # Half a line-width inset keeps adjacent lines from overlapping.
        for side in (-1, 1):
            box(f"{bay_id}_Side_{side}", (0.0, side * (BAY_WIDTH / 2 - 0.035), marking_z), (BAY_LENGTH, 0.06, 0.008), site_collection, bay, MATS["road_line"], "parking_marking")
        box(f"{bay_id}_End", (-BAY_LENGTH / 2 + 0.035, 0.0, marking_z), (0.06, BAY_WIDTH - 0.14, 0.008), site_collection, bay, MATS["road_line"], "parking_marking")
        if index % 4 == 0 or index in (5, 10, 15):
            # Shared placement records guarantee cars and markings agree.
            add_car(f"CAR_{index:02d}", (x, y), heading, colors[index % len(colors)], site_collection, site)
            bpy.data.objects[f"CAR_{index:02d}"]["bay_id"] = bay_id
    site["parking_bays"] = len(bays)
    for x, y, width in ((-23.0, -29.0, 7.0), (23.0, -29.0, 7.0), (-35.0, 14.0, 6.0), (35.0, 36.0, 6.0)):
        box(f"SITE_PlantingIsland_{x}_{y}", (x, y, 0.14), (width, 4.6, 0.12), site_collection, site, MATS["grass_bright"], "planted_island", 0.28)
    for side, fence_y in ((-1, -37.9), (1, 64.0)):
        for index in range(-6, 7):
            cylinder(f"SITE_FencePost_{side}_{index}", (index * 9.0, fence_y, 1.0), 0.035, 2.0, site_collection, site, MATS["frame"], 8, role="perimeter_fence")
        box(f"SITE_FenceRail_{side}", (0.0, fence_y, 1.4), (112.0, 0.04, 0.06), site_collection, site, MATS["frame"], "perimeter_fence")
    trees = [(-49, -27, 1.4), (-47, -7, 1.15), (-49, 16, 1.35), (-47, 42, 1.5), (49, -27, 1.3), (48, -6, 1.1), (49, 15, 1.45), (47, 37, 1.2), (48, 56, 1.5), (-33, 57, 1.0), (-15, 58, 1.2), (16, 58, 1.05), (33, 57, 1.25)]
    for index, (x, y, scale) in enumerate(trees):
        add_tree(f"TREE_{index:02d}", (x, y), scale, site_collection, site)
    # Linked meshes extend the landscape without duplicating leaf geometry in
    # the GLB. Their placement is context, not surveyed neighboring geography.
    templates = [obj for obj in site.children if obj.get("role") == "landscape_tree"]
    perimeter = [(side * (65 + (i % 3) * 7), -20 + i * 12) for side in (-1, 1) for i in range(9)]
    perimeter += [(-65 + i * 12, 78 + (i % 3) * 5) for i in range(12)]
    for index, (x, y) in enumerate(perimeter):
        tree = empty(f"CONTEXT_TREE_{index:02d}", site_collection, site, (x, y, 0), "landscape_tree", inferred_context=True)
        tree.rotation_euler.z = index * 2.4
        tree.scale = (1.2, 1.2, 1.2)
        for part in templates[index % len(templates)].children:
            linked = part.copy()
            linked.name = f"CONTEXT_TREE_{index:02d}_{part.get('role')}"
            site_collection.objects.link(linked)
            linked.parent = tree
    for index, x in enumerate((-29.0, 29.0)):
        box(f"SITE_Bin_{index}", (x, -29.4, 0.65), (1.1, 1.1, 1.3), site_collection, site, MATS["charcoal"], "site_bin", 0.08)
        box(f"SITE_BinLid_{index}", (x, -29.4, 1.36), (1.2, 1.2, 0.08), site_collection, site, MATS["frame"], "site_bin")
    add_marketing_banner("SITE_EntranceMarketing", (0.0, -30.4), 1.0, site_collection, site)
    add_marketing_banner("SITE_SideMarketing", (-28.0, -26.2), 0.72, site_collection, site)


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
    # Never recolor a world that another scene/user object already uses.
    scene.world = bpy.data.worlds.new("INTERMEDIA_Daylight")
    scene.world.use_nodes = True
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
    revision_input = Path(__file__).read_bytes()
    if GLB_PATH.exists():
        revision_input += b"\0" + GLB_PATH.read_bytes()
    manifest = {
        "schemaVersion": 1,
        "sceneVersion": SCENE_VERSION,
        "assetRevision": hashlib.sha256(revision_input).hexdigest()[:12],
        "units": "meters",
        "coordinateSystem": "Blender Z-up authoring, glTF Y-up export",
        "source": "INTERMEDIA reference renders and supplied marketing brief",
        "release": {
            "browserModel": "assets/intermedia-residential.glb",
            "sceneSource": "../blender/exports/intermedia-residential.blend",
            "manifest": "assets/intermedia-residential.json",
            "licenses": "assets/licenses.json",
            "collision": "Embedded nodes with role=collision; viewer uses triangle raycasting",
            "bakedLighting": None,
        },
        "bounds": {
            "siteMeters": {"min": [-60.0, -38.0, -0.62], "max": [60.0, 66.0, -0.06]},
            "buildingFootprintMeters": {"width": BUILDING_WIDTH, "depth": BUILDING_DEPTH, "height": TOTAL_HEIGHT + 0.9},
        },
        "lighting": {"daySunNode": None, "browserSunIntensity": 3.0, "exportedLights": False, "interiorBaking": "not bundled; browser uses authored materials and viewer lights"},
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
        "glass": material("MAT-Glass-Cool", (0.38, 0.46, 0.49), 0.18, 0.0, alpha=0.28),
        "glass_dark": material("MAT-Glass-Dark", (0.025, 0.055, 0.070), 0.12, 0.25, alpha=0.8),
        "curtain": material("MAT-Curtain-Warm", (0.68, 0.47, 0.28), 0.95),
        "asphalt": material("MAT-Asphalt", (0.055, 0.065, 0.075), 0.92, texture_kind="asphalt"),
        "paving": material("MAT-Paving", (0.46, 0.48, 0.46), 0.85),
        "road_line": material("MAT-Road-Line", (0.88, 0.85, 0.75), 0.68),
        "grass": material("MAT-Grass-Base", (0.12, 0.23, 0.08), 0.96, texture_kind="grass"),
        "grass_bright": material("MAT-Grass-Bright", (0.16, 0.34, 0.11), 0.92, texture_kind="grass"),
        "trunk": material("MAT-Tree-Trunk", (0.18, 0.075, 0.028), 0.98),
        "leaf": material("MAT-Tree-Leaf", (0.04, 0.20, 0.06), 0.96),
        "leaf_dark": material("MAT-Tree-Leaf-Dark", (0.018, 0.085, 0.035), 0.98),
        "leaf_light": material("MAT-Tree-Leaf-Light", (0.10, 0.26, 0.07), 0.92),
        "rubber": material("MAT-Rubber", (0.008, 0.012, 0.015), 0.90),
        "alloy": material("MAT-Wheel-Alloy", (0.48, 0.51, 0.53), 0.25, 0.82),
        "car_glass": material("MAT-Car-Glass", (0.035, 0.065, 0.08), 0.16, 0.25),
        "taillight": material("MAT-Taillight", (0.58, 0.012, 0.008), 0.22),
        "headlight": material("MAT-Headlight", (0.94, 0.82, 0.51), 0.18),
        "car_red": material("MAT-Car-Red", (0.56, 0.045, 0.025), 0.30, 0.16),
        "car_white": material("MAT-Car-White", (0.75, 0.78, 0.76), 0.28, 0.12),
        "car_blue": material("MAT-Car-Blue", (0.055, 0.22, 0.42), 0.28, 0.18),
        "car_yellow": material("MAT-Car-Yellow", (0.70, 0.48, 0.035), 0.30, 0.12),
        "car_silver": material("MAT-Car-Silver", (0.42, 0.46, 0.49), 0.24, 0.30),
        "car_dark": material("MAT-Car-Dark", (0.055, 0.07, 0.09), 0.25, 0.26),
        "wood_floor": material("MAT-Interior-WoodFloor", (0.50, 0.32, 0.16), 0.76, texture_kind="wood"),
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
    """Write only owned objects, without saving over the user's open file."""
    ensure_dir(EXPORT_DIR)
    ensure_dir(BLEND_PATH.parent)
    source_scene = bpy.context.scene
    candidate_glb = GLB_PATH.with_name("intermedia-residential.candidate.glb")
    candidate_blend = BLEND_PATH.with_name("intermedia-residential.candidate.blend")
    selected = list(bpy.context.selected_objects)
    active = bpy.context.view_layer.objects.active
    export_scene = bpy.data.scenes.new("INTERMEDIA_Export")
    try:
        owned = [obj for obj in source_scene.objects if obj.get("intermedia_owned")]
        if any(obj.parent and not obj.parent.get("intermedia_owned") for obj in owned):
            raise ValueError("Owned export object has a foreign parent")
        for obj in owned:
            export_scene.collection.objects.link(obj)
        export_scene.world = source_scene.world
        export_scene.camera = source_scene.camera if source_scene.camera in owned else None
        export_scene.unit_settings.system = "METRIC"
        export_scene.unit_settings.length_unit = "METERS"
        for key in source_scene.keys():
            if key != "_RNA_UI":
                export_scene[key] = source_scene[key]
        # Blender 5.2's partial scene writer assumes its view layer is synced.
        # Writing a newly linked but unevaluated scene crashes natively in
        # BKE_view_layer_copy_data; activate and evaluate it before library write.
        bpy.context.window.scene = export_scene
        bpy.context.view_layer.update()
        # A library write follows only the temporary scene's dependencies.
        # It neither exports unrelated collections nor changes bpy.data.filepath.
        bpy.data.libraries.write(str(candidate_blend), {export_scene}, fake_user=False, compress=True)
        for obj in export_scene.objects:
            obj.select_set(True)
        bpy.ops.export_scene.gltf(filepath=str(candidate_glb), export_format="GLB", use_selection=True, export_apply=True, export_materials="EXPORT", export_extras=True, export_lights=False, export_cameras=True, export_meshopt_compression_enable=True, export_meshopt_extension="EXT_meshopt_compression")
        import struct
        data = candidate_glb.read_bytes()
        assert data[:4] == b"glTF" and struct.unpack_from("<I", data, 8)[0] == len(data)
        length = struct.unpack_from("<I", data, 12)[0]
        gltf = json.loads(data[20:20 + length])
        names = {node.get("name") for node in gltf["nodes"]}
        assert all(f"BLK-{block}_F{floor}" in names for block in BUILDINGS for floor in range(4))
        assert any(mat.get("normalTexture") for mat in gltf["materials"])
        candidate_glb.replace(GLB_PATH)
        candidate_blend.replace(BLEND_PATH)
    finally:
        bpy.context.window.scene = source_scene
        bpy.data.scenes.remove(export_scene)
        for obj in source_scene.objects:
            obj.select_set(obj in selected)
        bpy.context.view_layer.objects.active = active


def main(*, export: bool = True) -> dict[str, object]:
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
    if export:
        export_files()
        build_manifest()
    owned_meshes = sum(1 for obj in bpy.data.objects if obj.type == "MESH" and obj.get("intermedia_owned"))
    return {"status": "exported" if export else "built_in_memory", "exported": export, "scene_version": SCENE_VERSION, "blend_path": str(BLEND_PATH), "glb_path": str(GLB_PATH), "manifest_path": str(MANIFEST_PATH), "owned_meshes": owned_meshes, "owned_objects": sum(1 for obj in bpy.data.objects if obj.get("intermedia_owned")), "materials": len(MATS), "textures": sum(1 for image in bpy.data.images if image.name.startswith("IMG-")), "buildings": list(BUILDINGS), "detailed_apartments": ["Studio", "2Room", "3Room"]}


# The normal MCP runner builds and exports. Helpers can load definitions with
# SKIP_BUILD or explicitly request an in-memory build with EXPORT=False.
if not globals().get("INTERMEDIA_SKIP_BUILD", False):
    result = main(export=bool(globals().get("INTERMEDIA_EXPORT", True)))
