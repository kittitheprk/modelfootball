import os
import sys
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import analyze_match


class TestHybridStability(unittest.TestCase):
    def test_hybrid_blending_is_clipped_and_stable(self):
        sim_v9 = {
            "model_version": "v9",
            "home_win_prob": 60.0,
            "draw_prob": 20.0,
            "away_win_prob": 20.0,
            "expected_goals_home": 3.5,
            "expected_goals_away": 0.35,
            "bonus_applied": "v9",
        }
        demo = {
            "enabled": True,
            "expected_goals_home": 5.6,
            "expected_goals_away": 0.05,
        }
        with mock.patch.dict(os.environ, {"HYBRID_DEMO_WEIGHT": "0.65"}, clear=False):
            hybrid, ctx = analyze_match._build_hybrid_sim(sim_v9, demo)
        self.assertIsNotNone(hybrid)
        self.assertTrue(ctx.get("enabled"))
        self.assertGreaterEqual(float(hybrid["expected_goals_home"]), 0.25)
        self.assertLessEqual(float(hybrid["expected_goals_home"]), 3.8)
        self.assertGreaterEqual(float(hybrid["expected_goals_away"]), 0.25)
        self.assertLessEqual(float(hybrid["expected_goals_away"]), 3.8)
        self.assertEqual(hybrid.get("model_version"), "hybrid_v10")
        self.assertIn("layers", ctx)

    def test_hybrid_unavailable_when_demo_missing(self):
        sim_v9 = {
            "model_version": "v9",
            "home_win_prob": 45.0,
            "draw_prob": 27.0,
            "away_win_prob": 28.0,
            "expected_goals_home": 1.5,
            "expected_goals_away": 1.2,
        }
        hybrid, ctx = analyze_match._build_hybrid_sim(sim_v9, {"enabled": False, "status": "unavailable"})
        self.assertIsNone(hybrid)
        self.assertFalse(ctx.get("enabled"))


if __name__ == "__main__":
    unittest.main()
