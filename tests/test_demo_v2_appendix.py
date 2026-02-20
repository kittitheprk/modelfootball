import os
import sys
import unittest

# Ensure we can import local modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import analyze_match


class TestDemoV2Appendix(unittest.TestCase):
    def test_appendix_unavailable_demo(self):
        sim_v9 = {
            "home_win_prob": 44.0,
            "draw_prob": 25.0,
            "away_win_prob": 31.0,
            "expected_goals_home": 1.55,
            "expected_goals_away": 1.25,
            "most_likely_score": "1-1",
        }
        demo = {
            "enabled": False,
            "status": "unavailable",
            "reason": "import_error",
            "league_used": "Premier_League",
            "adapter_context": {"source_confidence": 0.0},
        }
        text = analyze_match._build_model_comparison_appendix(
            "Arsenal",
            "Liverpool",
            sim_v9=sim_v9,
            demo_v2=demo,
            sim_hybrid=None,
            model_core_context={"active_core": "v9"},
        )
        self.assertIn("Model Core Comparison", text)
        self.assertIn("demo_v2 unavailable", text)
        self.assertIn("import_error", text)

    def test_appendix_with_comparison_and_deltas(self):
        sim_v9 = {
            "home_win_prob": 44.0,
            "draw_prob": 25.0,
            "away_win_prob": 31.0,
            "expected_goals_home": 1.55,
            "expected_goals_away": 1.25,
            "most_likely_score": "1-1",
            "bonus_applied": "v9",
        }
        demo = {
            "enabled": True,
            "model": "demo_model_v2",
            "league_used": "Premier_League",
            "home_win_prob": 46.2,
            "draw_prob": 24.3,
            "away_win_prob": 29.5,
            "home_win_prob_mc": 45.8,
            "draw_prob_mc": 24.5,
            "away_win_prob_mc": 29.7,
            "expected_goals_home": 1.62,
            "expected_goals_away": 1.19,
            "most_likely_score": "1-1",
            "home_rating_source": "Weighted (Home)",
            "away_rating_source": "Weighted (Away)",
            "adapter_context": {"source_confidence": 0.82},
        }
        sim_hybrid, _ = analyze_match._build_hybrid_sim(sim_v9, demo)
        text = analyze_match._build_model_comparison_appendix(
            "Arsenal",
            "Liverpool",
            sim_v9=sim_v9,
            demo_v2=demo,
            sim_hybrid=sim_hybrid,
            model_core_context={"active_core": "hybrid"},
        )
        self.assertIn("Active core: `hybrid`", text)
        self.assertIn("Delta demo_v2 vs v9", text)
        self.assertIn("Delta hybrid vs v9", text)
        self.assertIn("confidence=", text)


if __name__ == "__main__":
    unittest.main()
