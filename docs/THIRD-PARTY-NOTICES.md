# Third-party and brand notices

The repository contains original code and procedural scene output, but it
also points at tools, runtime libraries and a brand reference. These items are
not relicensed by the project’s MIT License.

## Runtime and authoring dependencies

| Dependency | Where it is used | Terms |
| --- | --- | --- |
| [Three.js](https://threejs.org/) | Browser viewer, loaded from the import map in dist/index.html | [MIT License](https://github.com/mrdoob/three.js/blob/dev/LICENSE) |
| [Blender](https://www.blender.org/) | Scene authoring and export | [GNU GPL v3 or later](https://www.blender.org/about/license/) for Blender itself; Blender is not bundled here |
| [Blender MCP](https://projects.blender.org/lab/blender_mcp) | Export bridge referenced by blender/mcp/pyproject.toml | Follow the upstream repository’s license and notices for the pinned revision |
| [Playwright](https://playwright.dev/) | Optional browser verification through npx | Follow the installed package’s license and notices |

The project does not redistribute the dependency source code. If a release
bundles or vendors a dependency in the future, its complete notice should be
added here before publishing that release.

## INTERMEDIA brand reference

The project uses the INTERMEDIA name, palette and architectural reference from
[vanzarialba.ro](https://www.vanzarialba.ro/) to create an illustrative
explorer. It does not redistribute the reference site’s logo asset. This use
does not grant a trademark license or imply endorsement.

The machine-readable asset record is [dist/assets/licenses.json](../dist/assets/licenses.json).
It records that the released GLB is project-owned procedural output and that
no third-party raster textures or paid model assets are bundled.

## Original project materials

Original source code, documentation, the README banner, and procedural scene
output are covered by the repository [MIT License](../LICENSE), subject to the
brand and dependency exceptions above.
