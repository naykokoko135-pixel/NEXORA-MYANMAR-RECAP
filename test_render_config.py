"""Regression tests for the Render Blueprint health-check configuration."""

from pathlib import Path
import unittest


class RenderBlueprintConfigTests(unittest.TestCase):
    def test_web_service_uses_health_endpoint_for_readiness(self):
        config = (Path(__file__).parent / "render.yaml").read_text(encoding="utf-8")

        self.assertIn("healthCheckPath: /health", config)

    def test_auto_deploy_waits_for_successful_checks(self):
        config = (Path(__file__).parent / "render.yaml").read_text(encoding="utf-8")

        self.assertIn("autoDeployTrigger: checksPass", config)


if __name__ == "__main__":
    unittest.main()
