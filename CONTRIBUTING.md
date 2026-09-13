# Contributing to INTERMEDIA residential explorer

Thanks for helping improve the explorer. Small documentation fixes, viewer
polish, scene improvements and careful validation are all welcome.

## Before you start

Please open an issue for a larger change so the intended experience and the
validation scope are clear before implementation. For a focused fix, a pull
request with a short explanation is enough.

When contributing scene or visual assets, confirm their provenance first. Add
the relevant creator, source and license to dist/assets/licenses.json; do not
commit an asset whose redistribution terms are unclear.

## Local setup

The released viewer is static and only needs a local HTTP server:

~~~sh
python3 -m http.server 4173 --directory dist
~~~

Open <http://127.0.0.1:4173/> and wait for the model to finish loading.

Blender scene work additionally needs Blender 5.1+, Python 3.10+, uv, and
the Blender Lab MCP add-on. The complete setup is in
[blender/README.md](blender/README.md).

## A healthy change loop

1. Keep the editable source and the released artifacts in sync. Scene changes
   start in blender/scene/build_scene.py and are exported through the MCP
   runner; do not hand-edit the GLB.
2. Run the asset validator and JavaScript syntax check:

   ~~~sh
   python3 scripts/validate_assets.py
   node --check dist/viewer.js
   ~~~

3. For Blender changes, run the geometry checks in a disposable Blender
   process when Blender is available:

   ~~~sh
   /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --python blender/scene/check_build_scene.py
   ~~~

4. For interaction changes, use the browser check described in the root
   [README.md](README.md) and record meaningful new evidence in docs/.
5. Check the narrow layout, keyboard focus, language picker, reduced-motion
   behavior and the illustrative-model disclaimer before opening a PR.

## Pull requests

Please include:

- a concise summary of the user-facing change;
- the commands you ran and their results;
- screenshots or a short recording for visual or interaction changes;
- updated documentation and asset notices when behavior or provenance changes.

Keep generated QA captures out of commits. They belong under the ignored
output/playwright/ directory. Avoid unrelated formatting or generated-file
churn in the same pull request.

## Design and content guardrails

- Preserve the blue, gold and airy architectural visual language unless the
  change is intentionally a redesign.
- Keep the 3D experience useful at narrow widths and with reduced motion.
- Treat inferred layouts, areas and site context as illustrative; do not turn
  them into survey-grade or construction-document claims.
- Keep user-facing copy friendly, concise and available in English and
  Romanian when it belongs to the viewer’s localization catalog.

By contributing, you agree that your original contributions may be distributed
under the repository’s [MIT License](LICENSE), subject to the notices in
[docs/THIRD-PARTY-NOTICES.md](docs/THIRD-PARTY-NOTICES.md).
