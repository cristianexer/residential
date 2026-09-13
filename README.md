# INTERMEDIA residential explorer

Bright, reference-based 3D presentation of the INTERMEDIA residential complex.
The editable scene is generated in Blender through the Blender Lab MCP runner;
the browser release is a Three.js WebGL2 viewer with semantic GLB metadata.

## GitHub Pages

The site is a static GitHub Pages build. The workflow at
`.github/workflows/pages.yml` publishes `dist/` whenever `main` is updated.
Enable GitHub Pages in the repository settings with **Source: GitHub Actions**;
after the first successful workflow run, GitHub will provide the public URL.

For a local preview (HTTP is required for GLB loading):

```sh
python3 -m http.server 4173 --directory dist
```

Open `http://127.0.0.1:4173/` and use the Exterior, Exploded, Cutaway and Floors
controls. English is the default interface language; use the flag picker in the
top bar to switch to Romanian. Select a block or one of the three furnished in-building homes;
the remaining illustrative flats also carry reusable kitchen, living, sleeping
and bathroom furniture sets. Dimensional INTERMEDIA marketing signs live in
the 3D site scene near the entrance and parking edge. Click a visible component
for its inspector, framing and isolation controls.
The single blue-to-gold bottom slider controls separation, section position, or
floor level. Sections cap individual structural solids, not whole room voids.
Walkthrough uses floor-height and obstacle raycasts against architectural meshes.

## Rebuild and validation

The reproducible authoring command requires the Blender Lab MCP bridge:

```sh
python3 scripts/run_blender_mcp.py blender/scene/build_scene.py
python3 scripts/validate_assets.py
```

The validator checks the released GLB header, hierarchy, semantic metadata,
finite transforms, embedded textures, UV channels and the verified studio
areas before the Pages workflow uploads `dist/`. Asset provenance is recorded in
`dist/assets/licenses.json`.

For an isolated export worker (still authored through Blender MCP):

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --command blender_mcp --port 9877
BLENDER_MCP_PORT=9877 python3 scripts/run_blender_mcp.py blender/scene/build_scene.py
```

The MCP server uses `BLENDER_MCP_HOST` / `BLENDER_MCP_PORT`. The unprefixed
`BLENDER_PORT` variable is not recognized by the Blender Lab server.
The runner preserves Python file context and reports export failures. Asset
revision hashes in the manifest prevent a rebuilt GLB being hidden by caching.

Geometry regression checks (fresh, disposable Blender process; no export):

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --python blender/scene/check_build_scene.py
```

Browser checks against the running HTTP preview:

```sh
npx --yes @playwright/cli -s=residential-check open http://127.0.0.1:4173/
npx --yes @playwright/cli -s=residential-check eval "$( < scripts/check-viewer.js)"
```

The browser check must run after the model finishes loading. It checks original
and rendered batch transforms, clipping/caps, picking, all building floors,
isolation and reset. See `docs/QA-2026-09-13.md` for scope and remaining limits.

The viewer preserves each logical GLB component for metadata and picking while
using material-scoped render batches where supported. It follows Three.js'
[BatchedMesh API](https://threejs.org/docs/pages/BatchedMesh.html); clipping
materials are scoped per building so context cannot inherit section effects.
The release uses EXT_meshopt_compression, decoded by the configured Three.js
Meshopt loader. Candidate GLB/Blender files are checked before replacing the
working artifacts; the manifest is updated only after a successful export.

The model is an illustrative P+3 architectural visualization based on the
supplied renders, not a survey-grade BIM or construction document. The studio
area and balcony area are taken from the supplied brief; other apartment areas,
room partitions and site context are explicitly inferred.
