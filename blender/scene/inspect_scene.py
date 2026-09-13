"""Read-only inspection script sent to the open Blender instance through MCP."""

import bpy


def collection_names(collection):
    names = [collection.name]
    for child in collection.children:
        names.extend(collection_names(child))
    return names


result = {
    "blender_version": bpy.app.version_string,
    "filepath": bpy.data.filepath,
    "scene": bpy.context.scene.name,
    "object_count": len(bpy.data.objects),
    "mesh_count": len(bpy.data.meshes),
    "material_count": len(bpy.data.materials),
    "collections": collection_names(bpy.context.scene.collection),
    "key_objects": [
        obj.name
        for obj in bpy.data.objects
        if any(token in obj.name for token in ("BLK-A", "BLK-B", "BLK-C", "UNIT-STUDIO", "UNIT-2ROOM", "UNIT-3ROOM"))
    ][:24],
}
