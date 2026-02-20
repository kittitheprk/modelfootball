import os
import sys
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import analyze_match


class TestModelCoreRouter(unittest.TestCase):
    def test_resolve_model_core_defaults_to_v9(self):
        with mock.patch.dict(os.environ, {"MODEL_CORE": "unknown_core"}, clear=False):
            core, ctx = analyze_match._resolve_model_core(default_core="v9")
        self.assertEqual(core, "v9")
        self.assertEqual(ctx.get("fallback_reason"), "unsupported_model_core_env")

    def test_resolve_model_core_hybrid_alias(self):
        with mock.patch.dict(os.environ, {"MODEL_CORE": "v10"}, clear=False):
            core, ctx = analyze_match._resolve_model_core(default_core="v9")
        self.assertEqual(core, "hybrid")
        self.assertEqual(ctx.get("resolved"), "hybrid")

    def test_select_active_sim_fallback_when_demo_unavailable(self):
        sim_v9 = {
            "model_version": "v9",
            "home_win_prob": 45.0,
            "draw_prob": 25.0,
            "away_win_prob": 30.0,
            "expected_goals_home": 1.5,
            "expected_goals_away": 1.2,
        }
        demo_v2 = {"enabled": False, "status": "unavailable", "reason": "import_error"}
        selected, ctx = analyze_match._select_active_sim(
            model_core="demo_v2",
            sim_v9=sim_v9,
            demo_v2=demo_v2,
            sim_hybrid=None,
            model_core_env_ctx={"requested": "demo_v2", "resolved": "demo_v2"},
        )
        self.assertEqual(ctx.get("active_core"), "v9")
        self.assertEqual(selected.get("model_version"), "v9")
        self.assertIn("fallback", str(ctx.get("fallback_reason")))


if __name__ == "__main__":
    unittest.main()
