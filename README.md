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

Open `http://127.0.0.1:4173/` and use the Exterior, Explodat, Secțiune and
Etaje controls. Select a block or one of the three furnished in-building homes;
Walkthrough enables eye-level WASD navigation with collision proxies.

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

The model is an illustrative P+3 architectural visualization based on the
supplied renders, not a survey-grade BIM or construction document. The studio
area and balcony area are taken from the supplied brief; other apartment areas,
room partitions and site context are explicitly inferred.
