import os
import sys
import unittest

import pandas as pd

# Ensure we can import local modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import simulator_v9
import update_tracker


class TestModelCalibration(unittest.TestCase):
    def test_build_calibration_from_predictions(self):
        df = pd.DataFrame(
            [
                {
                    "Date": "2026-02-10",
                    "League": "Serie_A",
                    "Home_Team": "Cagliari",
                    "Away_Team": "Lecce",
                    "Tactical_Regime": "high_press",
                    "Pred_Score": "1-0",
                    "Expected_Goals_Home": 1.2,
                    "Expected_Goals_Away": 0.9,
                    "Actual_Score": "0-2",
                },
                {
                    "Date": "2026-02-12",
                    "League": "Serie_A",
                    "Home_Team": "Lecce",
                    "Away_Team": "Cagliari",
                    "Tactical_Regime": "low_block",
                    "Pred_Score": "1-1",
                    "Expected_Goals_Home": 1.0,
                    "Expected_Goals_Away": 1.0,
                    "Actual_Score": "1-1",
                },
            ]
        )

        calib = update_tracker._build_calibration_from_predictions(df)
        self.assertIsInstance(calib, dict)
        self.assertIn("global", calib)
        self.assertIn("by_league", calib)
        self.assertIn("by_team", calib)
        self.assertIn("by_regime", calib)
        self.assertGreaterEqual(calib.get("source_rows_used", 0), 2)
        self.assertIn("Cagliari", calib["by_team"])
        self.assertIn("Lecce", calib["by_team"])
        self.assertIn("high_press", calib["by_regime"])

    def test_apply_model_calibration(self):
        calibration = {
            "global": {"home_scale": 1.03, "away_scale": 0.98},
            "by_league": {"Serie_A": {"home_scale": 1.01, "away_scale": 1.02}},
            "by_regime": {"high_press": {"home_scale": 1.02, "away_scale": 0.99, "reliability": 0.8}},
            "by_team": {
                "Cagliari": {"attack_scale": 0.94, "defense_scale": 1.07, "reliability": 0.8},
                "Lecce": {"attack_scale": 1.04, "defense_scale": 0.96, "reliability": 0.7},
            },
        }
        h, a, ctx = simulator_v9._apply_model_calibration(
            lambda_home=1.2,
            lambda_away=1.0,
            calibration=calibration,
            league="Serie_A",
            home_team="Cagliari",
            away_team="Lecce",
            tactical_regime="high_press",
        )
        self.assertNotEqual(round(h, 6), 1.2)
        self.assertNotEqual(round(a, 6), 1.0)
        self.assertTrue(ctx.get("enabled"))
        self.assertIn("home_multiplier", ctx)
        self.assertIn("away_multiplier", ctx)
        self.assertEqual(ctx.get("regime_key"), "high_press")


if __name__ == "__main__":
    unittest.main()
