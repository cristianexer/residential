"""Render one overview still from the saved scene for visual QA."""

from pathlib import Path

import bpy


output_path = Path("/Users/cristianexer/Hyperdrive/residential/output/playwright/blender-overview.png")
output_path.parent.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.render.filepath = str(output_path)
scene.render.resolution_percentage = 50
bpy.ops.render.render(write_still=True)

result = {
    "status": "rendered",
    "filepath": str(output_path),
    "width": scene.render.resolution_x,
    "height": scene.render.resolution_y,
    "resolution_percentage": scene.render.resolution_percentage,
}
