"""Production entrypoint: `python serve.py`.

The repository root *is* the ``nexora`` Python package (modules use relative imports). A flat checkout (as on Render or GitHub Actions)
therefore needs the package registered under its real name. The repo root also contains ``http.py``, which would shadow the standard
library if the root stayed on ``sys.path``, so it is removed before anything is imported.
"""
import asyncio
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != ROOT]


def load_package():
    if "nexora" not in sys.modules:
        spec = importlib.util.spec_from_file_location("nexora", os.path.join(ROOT, "__init__.py"), submodule_search_locations=[ROOT])
        mod = importlib.util.module_from_spec(spec)
        sys.modules["nexora"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["nexora"]


if __name__ == "__main__":
    load_package()
    from nexora import bot
    asyncio.run(bot.serve())
