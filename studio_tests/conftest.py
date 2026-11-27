"""Puts the repository root on sys.path and isolates all studio state in a temp dir."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp(prefix="nexora-test-")
for k in ("DATA_DIR", "WORK_DIR", "OUT_DIR", "STATE_DIR"):
    os.environ[k] = str(Path(_tmp) / k.lower())
os.environ["VOICE_PROFILE_DB_PATH"] = str(Path(_tmp) / "voices")
os.environ["NEXORA_ADMIN_PASSWORD"] = "test-admin-password-123"
os.environ["NEXORA_VIEWER_PASSWORD"] = "test-viewer-password-123"
for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "OPENAI_API_KEY", "GEMINI_API_KEY", "TMDB_API_KEY", "TMDB_API_READ_ACCESS_TOKEN", "OPENAI_MODEL"):
    os.environ.pop(k, None)
