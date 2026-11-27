"""Entrypoint for the acceptance harness (see studio/acceptance.py)."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != ROOT]
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location('nexora_serve', os.path.join(ROOT, 'serve.py'))
_serve = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_serve)
_serve.load_package()
from nexora.studio import acceptance  # noqa: E402

if __name__ == "__main__":
    sys.exit(acceptance.main())
