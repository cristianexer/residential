# Blender project setup

This project uses Blender Lab’s official MCP integration:

- Blender: 5.1 or newer. The local installation is Blender 5.2.1 LTS.
- Blender add-on: MCP 1.0.0, listening on `127.0.0.1:9876`.
- MCP server: Blender Lab `blender-mcp` 1.0.2, pinned to commit `ff54e4d`.
- Python: 3.10 or newer, managed for this setup by `uv`.

The root `.mcp.json` registers the server for MCP clients that support project
configuration. The server process is started on demand; Blender itself must be
open with the MCP add-on enabled and its bridge server running.

## One-time Blender setup

1. In Blender 5.1+, open `Edit > Preferences > Extensions > Get Extensions`.
2. Search for `MCP`, install the Blender Lab add-on, and enable it.
3. In the MCP add-on preferences, keep `Host` as `localhost`, `Port` as
   `9876`, and enable `Auto Start`.
4. If Blender reports that online access is disabled, enable
   `Preferences > System > Network > Allow Online Access`.

## Verify the connection

From the repository root:

```sh
uv sync --project blender/mcp
python3 scripts/verify-blender-mcp.py
```

The verification script performs an MCP initialize handshake, lists the
available Blender tools, and evaluates a read-only Python expression in the
running Blender session. It does not change the current scene.

## Exported explorer

The generated deliverables are:

- `blender/exports/intermedia-residential.blend` — editable Blender source.
- `dist/assets/intermedia-residential.glb` — browser-ready glTF binary.
- `dist/index.html` — the light INTERMEDIA Exterior / Explodat / Secțiune /
  Etaje explorer with apartment inspection and walkthrough navigation.

To preview the explorer locally, serve the `dist` directory over HTTP:

```sh
python3 -m http.server 4173 --directory dist
```

Then open `http://127.0.0.1:4173/`. The model is an illustrative P+3
architectural visualization based on the supplied renders; it is not a
survey-grade BIM or construction document. Studio dimensions are verified from
the supplied brief; missing layouts and site context are explicitly inferred.
