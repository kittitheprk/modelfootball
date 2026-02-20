import json
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestLatestPredictionSchema(unittest.TestCase):
    def test_latest_prediction_schema_regression(self):
        path = os.path.join(PROJECT_ROOT, "latest_prediction.json")
        self.assertTrue(os.path.exists(path), "latest_prediction.json not found")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        required_keys = [
            "Date",
            "Match",
            "League",
            "Home_Team",
            "Away_Team",
            "Pred_Home_Win",
            "Pred_Draw",
            "Pred_Away_Win",
            "Pred_Score",
            "Pred_Result",
            "Expected_Goals_Home",
            "Expected_Goals_Away",
            "Model_Version",
            "Bet_Data",
            "Bet_Detail",
            "Progression_Data",
            "Flow_Data",
            "Tactical_Scenarios",
            "Calibration_Context",
            "Simulator_Tactical_Context",
            "Demo_v2_Shadow",
            "XG_Input",
        ]
        for key in required_keys:
            self.assertIn(key, data, f"Missing key: {key}")

        self.assertTrue(
            ("Model_Core" in data and "Model_Core_Context" in data) or ("Model_Version" in data),
            "Model core routing context missing.",
        )


if __name__ == "__main__":
    unittest.main()
