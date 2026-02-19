import os
import sys
import unittest

# Ensure we can import local modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import simulator_v9
import xg_engine


class TestFullSystem(unittest.TestCase):
    def test_xg_to_simulator_pipeline(self):
        league = "Premier_League"
        eng = xg_engine.XGEngine(league)

        h_xg = eng.get_team_rolling_stats("Arsenal", n_games=5)
        a_xg = eng.get_team_rolling_stats("Liverpool", n_games=5)

        self.assertIsNotNone(h_xg, "Could not fetch xG stats for Arsenal")
        self.assertIsNotNone(a_xg, "Could not fetch xG stats for Liverpool")
        self.assertIn("attack", h_xg)
        self.assertIn("defense", h_xg)

        sim = simulator_v9.simulate_match(h_xg, a_xg, None, None, iterations=1000)
        self.assertIn("most_likely_score", sim)
        self.assertIn("home_win_prob", sim)
        self.assertIn("draw_prob", sim)
        self.assertIn("away_win_prob", sim)
        self.assertEqual(sim.get("model_version"), "v9")

        total_prob = sim["home_win_prob"] + sim["draw_prob"] + sim["away_win_prob"]
        self.assertAlmostEqual(total_prob, 100.0, delta=0.2)


if __name__ == "__main__":
    unittest.main()
