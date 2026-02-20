import os
import sys
import unittest

# Ensure we can import local modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import analyze_match


class TestDemoV2Appendix(unittest.TestCase):
    def test_appendix_unavailable(self):
        demo = {"enabled": False, "status": "unavailable", "reason": "import_error", "league_used": "Premier_League"}
        text = analyze_match._build_demo_v2_appendix("Arsenal", "Liverpool", demo, sim_v9=None)
        self.assertIn("Demo Model v2", text)
        self.assertIn("ไม่พร้อมใช้งาน", text)
        self.assertIn("Premier_League", text)

    def test_appendix_with_comparison(self):
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
        }
        sim_v9 = {
            "home_win_prob": 44.0,
            "draw_prob": 25.0,
            "away_win_prob": 31.0,
            "expected_goals_home": 1.55,
            "expected_goals_away": 1.25,
        }
        text = analyze_match._build_demo_v2_appendix("Arsenal", "Liverpool", demo, sim_v9=sim_v9)
        self.assertIn("รันสำเร็จ", text)
        self.assertIn("Comparison to v9", text)
        self.assertIn("Delta vs v9 (Home)", text)


if __name__ == "__main__":
    unittest.main()

