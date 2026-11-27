"""Entrypoint for the acceptance harness (see studio/acceptance.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from studio import acceptance  # noqa: E402

if __name__ == "__main__":
    sys.exit(acceptance.main())
