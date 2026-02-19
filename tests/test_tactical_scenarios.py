import os
import sys
import unittest

# Ensure we can import local modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import analyze_match


class TestTacticalScenarios(unittest.TestCase):
    def test_build_tactical_scenario_report(self):
        sim = {
            "expected_goals_home": 1.42,
            "expected_goals_away": 1.18,
        }
        home_flow = {
            "calc_PPDA": 4.8,
            "calc_FieldTilt_Pct": 0.42,
            "calc_HighError_Rate": 21,
            "calc_Directness": 0.10,
            "calc_BigChance_Diff": -5,
        }
        away_flow = {
            "calc_PPDA": 6.1,
            "calc_FieldTilt_Pct": 0.46,
            "calc_HighError_Rate": 18,
            "calc_Directness": 0.09,
            "calc_BigChance_Diff": -8,
        }
        home_squad = {"Poss": 53.0}
        away_squad = {"Poss": 47.0}
        home_prog = {
            "xt_proxy": 0.54,
            "counter_punch_index": 0.33,
            "u_shape_risk": 0.27,
            "deep_completion_proxy": 4.4,
            "prg_carry_dist": 5.9,
            "big_created_p90": 1.8,
            "inside_box_shots_p90": 5.4,
            "fast_breaks_p90": 1.6,
            "corners_p90": 4.8,
            "long_balls_p90": 32.0,
            "shots_on_target_p90": 3.7,
        }
        away_prog = {
            "xt_proxy": 0.47,
            "counter_punch_index": 0.29,
            "u_shape_risk": 0.35,
            "deep_completion_proxy": 3.8,
            "prg_carry_dist": 5.2,
            "big_created_p90": 1.5,
            "inside_box_shots_p90": 4.6,
            "fast_breaks_p90": 1.2,
            "corners_p90": 4.1,
            "long_balls_p90": 30.0,
            "shots_on_target_p90": 3.1,
        }

        report = analyze_match.build_tactical_scenario_report(
            home_team="Home FC",
            away_team="Away FC",
            sim=sim,
            home_flow=home_flow,
            away_flow=away_flow,
            home_squad=home_squad,
            away_squad=away_squad,
            home_prog=home_prog,
            away_prog=away_prog,
            home_top_rated=["Creator One (Rating 7.45)"],
            away_top_rated=["Creator Two (Rating 7.20)"],
            max_scenarios=6,
        )

        self.assertIsInstance(report, dict)
        self.assertIn("scenarios", report)
        self.assertGreaterEqual(len(report["scenarios"]), 4)

        has_press = False
        for sc in report["scenarios"]:
            self.assertIn("probability_pct", sc)
            self.assertIn("goal_probability_pct", sc)
            self.assertGreaterEqual(sc["probability_pct"], 0.0)
            self.assertLessEqual(sc["probability_pct"], 100.0)
            self.assertGreaterEqual(sc["goal_probability_pct"], 0.0)
            self.assertLessEqual(sc["goal_probability_pct"], 100.0)
            if sc.get("scenario_code") == "press_to_wide_release":
                has_press = True
                self.assertIn("statistical_basis", sc)
        self.assertTrue(has_press, "Expected press_to_wide_release scenario")


if __name__ == "__main__":
    unittest.main()
