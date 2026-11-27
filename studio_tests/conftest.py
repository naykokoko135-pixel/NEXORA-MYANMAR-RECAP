"""Registers the repository root as the ``nexora`` package (see serve.py) and isolates all state in a temp dir."""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != ROOT]
_tmp = tempfile.mkdtemp(prefix="nexora-test-")
for k in ("DATA_DIR", "WORK_DIR", "OUT_DIR", "STATE_DIR"):
    os.environ[k] = str(Path(_tmp) / k.lower())
os.environ["VOICE_PROFILE_DB_PATH"] = str(Path(_tmp) / "voices")
os.environ["NEXORA_ADMIN_PASSWORD"] = "test-admin-password-123"
os.environ["NEXORA_VIEWER_PASSWORD"] = "test-viewer-password-123"
for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "OPENAI_API_KEY", "GEMINI_API_KEY", "TMDB_API_KEY"):
    os.environ.pop(k, None)
if "nexora" not in sys.modules:
    spec = importlib.util.spec_from_file_location("nexora", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nexora"] = mod
    spec.loader.exec_module(mod)
