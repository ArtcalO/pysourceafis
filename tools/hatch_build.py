"""Hatchling build hook: make sure the jars exist before a wheel is built."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class JarBuildHook(BuildHookInterface):
    PLUGIN_NAME = "custom"

    def initialize(self, version, build_data):
        root = Path(self.root)
        script = root / "tools" / "build_jars.py"
        verified = subprocess.run([sys.executable, str(script), "--check"], capture_output=True).returncode == 0
        if not verified:
            self.app.display_info("pysourceafis: building jars (tools/build_jars.py)...")
            subprocess.run([sys.executable, str(script)], check=True)
        if version != "editable":
            # The wheel contains jars but no compiled code, so it is platform independent.
            build_data["pure_python"] = True
