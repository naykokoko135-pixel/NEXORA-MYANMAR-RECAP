"""Central opt-in guard for APIs that may incur usage charges."""
import os


def paid_ai_allowed():
    """Paid AI calls are disabled unless the owner explicitly opts in."""
    return os.getenv("NEXORA_ALLOW_PAID_AI", "").strip().casefold() in {"1", "true", "yes", "on"}
