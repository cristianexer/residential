#!/usr/bin/env python3
"""Validate the browser export before it is published.

This intentionally has no third-party dependencies so it can run in GitHub
Actions and in the Blender/MCP authoring checkout alike.
"""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GLB_PATH = ROOT / "dist/assets/intermedia-residential.glb"
MANIFEST_PATH = ROOT / "dist/assets/intermedia-residential.json"
HTML_PATH = ROOT / "dist/index.html"
LICENSE_PATH = ROOT / "dist/assets/licenses.json"


def read_glb(path: Path) -> dict:
    data = path.read_bytes()
    if len(data) < 20 or data[:4] != b"glTF":
        raise AssertionError(f"invalid GLB header: {path}")
    version, length = struct.unpack_from("<II", data, 4)
    if version != 2 or length != len(data):
        raise AssertionError(f"unexpected GLB version/length: {version}/{length}")
    offset = 12
    json_chunk = None
    while offset + 8 <= len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        payload = data[offset + 8 : offset + 8 + chunk_length]
        if chunk_type == 0x4E4F534A:
            json_chunk = json.loads(payload.decode("utf-8"))
        offset += 8 + chunk_length
    if json_chunk is None:
        raise AssertionError("GLB has no JSON chunk")
    return json_chunk


def assert_finite(value: object, label: str) -> None:
    if isinstance(value, (int, float)) and not math.isfinite(value):
        raise AssertionError(f"non-finite {label}: {value}")
    if isinstance(value, list):
        for index, item in enumerate(value):
            assert_finite(item, f"{label}[{index}]")


def main() -> None:
    gltf = read_glb(GLB_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text())
    licenses = json.loads(LICENSE_PATH.read_text())
    html = HTML_PATH.read_text()

    nodes = gltf.get("nodes", [])
    meshes = gltf.get("meshes", [])
    materials = gltf.get("materials", [])
    images = gltf.get("images", [])
    textures = gltf.get("textures", [])
    assert len(nodes) >= 2_500, f"hierarchy unexpectedly small: {len(nodes)} nodes"
    assert len(meshes) >= 2_400, f"mesh export unexpectedly small: {len(meshes)} meshes"
    assert len(materials) >= 40, f"material library unexpectedly small: {len(materials)} materials"
    assert len(images) >= 8 and len(textures) >= 8, "embedded texture set is incomplete"

    names = {node.get("name") for node in nodes}
    required_names = {
        "INTERMEDIA_PROJECT",
        "SITE",
        "BLK-A",
        "BLK-B",
        "BLK-C",
        "BLK-A_F0",
        "BLK-A_F1",
        "BLK-A_F2",
        "BLK-A_F3",
        "BLK-A_ROOF",
        "UNIT-STUDIO",
        "UNIT-2ROOM",
        "UNIT-3ROOM",
        "COLLISION",
    }
    missing = sorted(required_names - names)
    assert not missing, f"required semantic nodes missing: {missing}"

    extras_count = 0
    for index, node in enumerate(nodes):
        assert_finite(node.get("translation", []), f"node[{index}].translation")
        assert_finite(node.get("rotation", []), f"node[{index}].rotation")
        assert_finite(node.get("scale", []), f"node[{index}].scale")
        if node.get("extras"):
            extras_count += 1
    assert extras_count >= 2_500, "semantic metadata was lost from the hierarchy"

    primitives = [primitive for mesh in meshes for primitive in mesh.get("primitives", [])]
    missing_uv = sum("TEXCOORD_0" not in primitive.get("attributes", {}) for primitive in primitives)
    assert not missing_uv, f"{missing_uv} exported primitives have no UV channel"

    assert manifest.get("sceneVersion") == "2.0.0"
    assert manifest.get("release", {}).get("browserModel") == "assets/intermedia-residential.glb"
    assert manifest.get("release", {}).get("collision")
    assert manifest.get("lighting", {}).get("daySunNode") == "LGT-DaySun"
    verified = manifest.get("verified", {})
    assert verified.get("buildingCount") == 3
    assert verified.get("buildingLevels") == "P+3"
    assert abs(float(verified.get("studioUsableAreaM2", 0)) - 30.30) <= 0.05
    assert abs(float(verified.get("studioBalconyAreaM2", 0)) - 6.60) <= 0.05
    for unit_name in ("Studio", "2Room", "3Room"):
        assert unit_name in manifest.get("apartments", {})
    assert licenses.get("schemaVersion") == 1
    assert licenses.get("externalAssets") == []
    assert "file://" not in html, "viewer should be opened through HTTP, not file://"
    assert "intermedia-residential.glb" in html, "viewer does not reference the released GLB"

    print(
        "asset validation passed: "
        f"{len(nodes)} nodes, {len(meshes)} meshes, {len(materials)} materials, "
        f"{len(images)} embedded images, {len(primitives)} UV-mapped primitives"
    )


if __name__ == "__main__":
    main()
