"""Re-export the current owned scene through MCP without regenerating geometry."""
import runpy
from pathlib import Path

namespace = runpy.run_path(str(Path(__file__).with_name("build_scene.py")),
                          init_globals={"INTERMEDIA_SKIP_BUILD": True})
namespace["export_files"]()
namespace["build_manifest"]()
result = {"status": "exported", "glb": str(namespace["GLB_PATH"])}
