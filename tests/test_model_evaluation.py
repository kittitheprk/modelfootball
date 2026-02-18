import os
import sys
import unittest

import pandas as pd

# Ensure we can import local modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import update_tracker


class TestModelEvaluation(unittest.TestCase):
    def test_normalize_1x2_probs(self):
        p_home, p_draw, p_away = update_tracker._normalize_1x2_probs(40.0, 30.0, 30.0)
        self.assertAlmostEqual(p_home + p_draw + p_away, 1.0, places=8)
        self.assertAlmostEqual(p_home, 0.4, places=6)
        self.assertAlmostEqual(p_draw, 0.3, places=6)
        self.assertAlmostEqual(p_away, 0.3, places=6)

    def test_evaluate_prediction_rows(self):
        df = pd.DataFrame(
            [
                {
                    "League": "Serie_A",
                    "Pred_Home_Win%": 40.0,
                    "Pred_Draw%": 30.0,
                    "Pred_Away_Win%": 30.0,
                    "Pred_Result": "Home",
                    "Pred_Score": "1-0",
                    "Expected_Goals_Home": 1.3,
                    "Expected_Goals_Away": 0.9,
                    "Actual_Score": "0-2",
                    "Actual_Result": "Away",
                },
                {
                    "League": "Serie_A",
                    "Pred_Home_Win%": 30.0,
                    "Pred_Draw%": 25.0,
                    "Pred_Away_Win%": 45.0,
                    "Pred_Result": "Away",
                    "Pred_Score": "1-2",
                    "Expected_Goals_Home": 1.0,
                    "Expected_Goals_Away": 1.4,
                    "Actual_Score": "2-3",
                    "Actual_Result": "Away",
                },
            ]
        )

        out = update_tracker._evaluate_prediction_rows(df)
        overall = out.get("overall", {})
        self.assertEqual(overall.get("n_matches"), 2)
        self.assertIn("brier_1x2", overall)
        self.assertIn("log_loss_1x2", overall)
        self.assertIn("score_mae", overall)
        self.assertIn("Serie_A", out.get("by_league", {}))


if __name__ == "__main__":
    unittest.main()
