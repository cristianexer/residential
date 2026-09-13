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
    assert nodes and meshes, "empty model"
    assert len(nodes) >= 4_000, f"scene hierarchy unexpectedly small: {len(nodes)} nodes"
    assert len(meshes) >= 4_000, f"scene geometry unexpectedly small: {len(meshes)} meshes"
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
    assert extras_count >= len(nodes) * 0.95, "semantic metadata was lost from the hierarchy"

    primitives = [primitive for mesh in meshes for primitive in mesh.get("primitives", [])]
    missing_uv = sum("TEXCOORD_0" not in primitive.get("attributes", {}) for primitive in primitives)
    assert not missing_uv, f"{missing_uv} exported primitives have no UV channel"

    assert manifest.get("sceneVersion") in ("2.0.0", "2.1.0")
    assert manifest.get("release", {}).get("browserModel") == "assets/intermedia-residential.glb"
    assert manifest.get("release", {}).get("collision")
    assert manifest.get("lighting", {}).get("exportedLights") is False
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
    assert '<html lang="en">' in html, "English must be the default document language"
    viewer = (ROOT / "dist/viewer.js").read_text()
    assert "intermedia-residential.glb" in viewer, "viewer does not reference the released GLB"
    assert 'role="listbox"' in viewer and "component-picker-button" in viewer, "component picker is not the branded custom listbox"
    assert "quality-picker-button" in viewer and "quality-list" in viewer and "quality-select" not in html, "quality picker is not the branded custom listbox"
    assert "axis-picker-button" in viewer and "axis-list" in viewer and "section-axis" not in html, "section orientation is not the branded custom listbox"
    assert "language-picker-button" in html and "language-list" in html and 'data-language="ro"' in html and "🇬🇧" in html and "🇷🇴" in html, "flag language switcher is missing"
    assert "setLanguage" in viewer and 'language:"en"' in viewer, "viewer language state is incomplete"
    assert "selectionMarker" in viewer, "selected-element marker is missing"
    assert "SITE_EntranceMarketing" in names and "SITE_SideMarketing" in names, "3D marketing banners missing"
    assert "promo-banner" not in html, "marketing banner should live in the 3D scene, not the sidebar"
    assert html.count('type="range"') == 1, "the dock must have exactly one functional layer slider"
    assert 'class="progress-track"' not in html, "duplicate decorative track returned"
    for block in ("A", "B", "C"):
        building_index = next(i for i,n in enumerate(nodes) if n.get("name") == f"BLK-{block}")
        children = nodes[building_index].get("children", [])
        for floor in range(4):
            floor_index = next(i for i,n in enumerate(nodes) if n.get("name") == f"BLK-{block}_F{floor}")
            assert floor_index in children, "floor must be parented to its building"
            assert nodes[floor_index].get("extras", {}).get("floor_index") == floor
    if manifest.get("lighting", {}).get("exportedLights") is False:
        assert not any("_GraphiteField" in str(n) or "_GroundBand" in str(n) for n in names), "opaque facade overlays returned"
        assert any("WhiteTrim" in str(n) for n in names), "window surrounds missing"
        assert any(m.get("normalTexture") for m in materials), "surface normal maps missing"

    print(
        "asset validation passed: "
        f"{len(nodes)} nodes, {len(meshes)} meshes, {len(materials)} materials, "
        f"{len(images)} embedded images, {len(primitives)} UV-mapped primitives"
    )


if __name__ == "__main__":
    main()
