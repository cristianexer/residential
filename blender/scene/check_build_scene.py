"""In-memory geometry checks; run in Blender --background --factory-startup.

Never connects to the user's Blender session and never saves/exports assets.
"""

import json
import runpy
from pathlib import Path

import bpy
from mathutils import Vector


def bounds(obj, transform=None):
    transform = transform if transform is not None else obj.matrix_world
    points = [transform @ Vector(corner) for corner in obj.bound_box]
    return tuple(min(p[i] for p in points) for i in range(3)), tuple(max(p[i] for p in points) for i in range(3))


def overlaps(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0) > 1e-5


ns = runpy.run_path(str(Path(__file__).with_name("build_scene.py")), init_globals={"INTERMEDIA_SKIP_BUILD": True})
original_objects = set(bpy.data.objects)
result = ns["main"](export=False)
bpy.context.view_layer.update()
assert not result["exported"]
assert original_objects <= set(bpy.data.objects)
materials = ns["main"].__globals__["MATS"]
for mat in materials.values():
    if mat.get("texture_kind") in ("brick", "wood", "tile", "asphalt"):
        normal_maps = [node for node in mat.node_tree.nodes if node.type == "NORMAL_MAP"]
        assert len(normal_maps) == 1
        normal_image = normal_maps[0].inputs["Color"].links[0].from_node.image
        assert normal_image.colorspace_settings.name == "Non-Color" and normal_image.packed_file
        assert normal_maps[0].outputs["Normal"].is_linked
owned = [obj for obj in bpy.data.objects if obj.get("intermedia_owned")]
meshes = [obj for obj in owned if obj.type == "MESH"]

# Validate all bodywork, mirrors, rims and wheels against the same bay frame.
cars = [obj for obj in owned if obj.get("role") == "vehicle"]
bays = [obj for obj in owned if obj.get("role") == "parking_bay"]
for car in cars:
    bay = bpy.data.objects[car["bay_id"]]
    for part in car.children:
        lo, hi = bounds(part, bay.matrix_world.inverted() @ part.matrix_world)
        assert lo[0] >= -2.5 and hi[0] <= 2.5, part.name
        assert lo[1] >= -1.25 and hi[1] <= 1.25, part.name
        if part.get("role") == "vehicle_wheel":
            assert abs(bounds(part)[0][2] - ns["COURT_TOP"]) < 1e-5, part.name
for bay in bays:
    corners = [bay.matrix_world @ Vector((x, y, 0)) for x in (-2.5, 2.5) for y in (-1.25, 1.25)]
    x0, x1 = min(p.x for p in corners), max(p.x for p in corners)
    y0, y1 = min(p.y for p in corners), max(p.y for p in corners)
    for center in ns["BUILDINGS"].values():
        assert not (overlaps(x0, x1, -14.22, 14.22) and overlaps(y0, y1, center - 6.72, center + 6.72)), bay.name
for mesh in meshes:
    if mesh.get("role") == "parking_marking":
        assert bounds(mesh)[0][2] > ns["COURT_TOP"] + 0.005
    if mesh.get("role") == "access_court":
        lo, hi = bounds(mesh)
        for center in ns["BUILDINGS"].values():
            assert not (overlaps(lo[0], hi[0], -14.2, 14.2) and overlaps(lo[1], hi[1], center - 6.7, center + 6.7)), mesh.name

# Check the actual faces, not wall AABBs (a wall mesh spans several openings).
windows = [obj for obj in meshes if obj.get("role") == "window_glazing"]
for window in windows:
    axis = 1 if window.parent.get("facade_side") in ("left", "right") else 0
    lo, hi = bounds(window, window.matrix_local)
    for wall in window.parent.children:
        if wall.get("role") not in ("exterior_wall", "facade_trim"):
            continue
        for polygon in wall.data.polygons:
            points = [wall.matrix_local @ wall.data.vertices[index].co for index in polygon.vertices]
            u0, u1 = min(p[axis] for p in points), max(p[axis] for p in points)
            z0, z1 = min(p.z for p in points), max(p.z for p in points)
            assert not (overlaps(lo[axis], hi[axis], u0, u1) and overlaps(lo[2], hi[2], z0, z1)), (window.name, wall.name)

balconies = [obj for obj in owned if obj.get("role") == "balcony"]
pipes = [obj for obj in owned if obj.get("role") == "roof_downpipe"]
assert len(balconies) == 18
for balcony in balconies:
    slab = next(child for child in balcony.children_recursive if child.get("role") == "balcony_slab")
    slab_lo, slab_hi = bounds(slab)
    assert slab_hi[0] - slab_lo[0] >= 4.9, balcony.name
    for pipe in pipes:
        pipe_lo, pipe_hi = bounds(pipe)
        assert not (
            overlaps(slab_lo[0], slab_hi[0], pipe_lo[0], pipe_hi[0])
            and overlaps(slab_lo[1], slab_hi[1], pipe_lo[1], pipe_hi[1])
            and overlaps(slab_lo[2], slab_hi[2], pipe_lo[2], pipe_hi[2])
        ), (balcony.name, pipe.name)

for floor in [obj for obj in owned if obj.get("role") == "floor"]:
    index = floor["floor_index"]
    slabs = [obj for obj in floor.children if obj.get("role") == "floor_slab"]
    ceilings = [obj for obj in floor.children if obj.get("role") == "ceiling"]
    for slab in slabs:
        lo, hi = bounds(slab, slab.matrix_local)
        assert abs(hi[2]) < 1e-5
        if index > 0:
            assert not (overlaps(lo[0], hi[0], -1.65, 1.65) and overlaps(lo[1], hi[1], -1.3, 3.2)), slab.name
    for ceiling in ceilings:
        lo, hi = bounds(ceiling, ceiling.matrix_local)
        assert hi[2] < ns["FLOOR_HEIGHTS"][index] - ns["SLAB_THICKNESS"] - 0.01
        if index < 3:
            assert not (overlaps(lo[0], hi[0], -1.65, 1.65) and overlaps(lo[1], hi[1], -1.3, 3.2)), ceiling.name
    treads = [obj for obj in floor.children_recursive if obj.get("role") == "stair_tread"]
    if index < 3:
        tops = sorted({round(bounds(obj)[1][2] - floor.location.z, 5) for obj in treads})
        assert len(tops) >= 18
        assert abs(tops[-1] - ns["FLOOR_HEIGHTS"][index] - ns["FINISH_TOP"]) < 1e-4
        assert max(b - a for a, b in zip(tops, tops[1:])) <= 0.19001
    else:
        assert not treads

trees = [obj for obj in owned if obj.get("role") == "landscape_tree"]
for tree in trees:
    assert len(tree.children) == 2, tree.name
    assert sum(len(obj.data.materials) for obj in tree.children) == 4, tree.name
assert not any(obj.get("role") == "facade_panel" for obj in owned)
for block, floor_index in ns["DETAILED_FLOORS"]:
    assert f"BLK-{block}_F{floor_index}_UNIT_L" not in bpy.data.objects

# Rebuild cleanup must retain user objects/collections even inside our tree.
root_collection = ns["main"].__globals__["ROOT"].users_collection[0]
user_collection = bpy.data.collections.new("User_Keep_Collection")
root_collection.children.link(user_collection)
user_object = bpy.data.objects.new("User_Keep_Object", None)
root_collection.objects.link(user_object)
user_object.parent = cars[0]
user_object.location = (0.2, 0.3, 0.4)
bpy.context.view_layer.update()
user_world = user_object.matrix_world.copy()
summary = {"checks": "passed", "meshes": len(meshes), "material_primitives": sum(max(1, len(obj.data.materials)) for obj in meshes), "windows": len(windows), "balconies": len(balconies), "cars": len(cars), "bays": len(bays), "trees": len(trees), "tree_meshes": 2 * len(trees), "exported": False}
ns["clear_owned_scene"]()
assert original_objects <= set(bpy.data.objects)
assert user_object.name in bpy.context.scene.objects
assert user_collection.name in bpy.context.scene.collection.children
assert all(abs(user_object.matrix_world[row][col] - user_world[row][col]) < 1e-5 for row in range(4) for col in range(4))
print(json.dumps(summary, sort_keys=True))
