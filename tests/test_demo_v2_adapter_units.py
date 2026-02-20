import os
import sys
import unittest

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import analyze_match


class TestDemoV2AdapterUnits(unittest.TestCase):
    def test_unit_policy_per_match_from_raw(self):
        df = pd.DataFrame(
            [
                {
                    "team_name": "Arsenal",
                    "matches_played": 10,
                    "expected_goals": 18.0,
                    "goalsconceded": 9.0,
                    "shots": 150.0,
                    "bigchances": 22.0,
                    "penaltygoals": 3.0,
                    "accuratepasses": 5200.0,
                }
            ]
        )
        out, report = analyze_match._apply_demo_v2_unit_policy(df, unit_policy="per_match")
        self.assertAlmostEqual(float(out.loc[0, "expected_goals"]), 1.8, places=6)
        self.assertAlmostEqual(float(out.loc[0, "goalsconceded"]), 0.9, places=6)
        self.assertEqual(report.get("unit_policy"), "per_match")
        self.assertGreater(report.get("coverage", 0.0), 0.0)

    def test_unit_policy_per_90_prefers_direct_column(self):
        df = pd.DataFrame(
            [
                {
                    "team_name": "Liverpool",
                    "matches_played": 10,
                    "expected_goals": 20.0,
                    "expected_goals_per_90": 1.65,
                    "goalsconceded": 11.0,
                    "goalsconceded_per_90": 0.95,
                    "shots": 160.0,
                    "shots_per_90": 14.2,
                    "bigchances": 24.0,
                    "bigchances_per_90": 2.1,
                    "penaltygoals": 4.0,
                    "penaltygoals_per_90": 0.3,
                    "accuratepasses": 5400.0,
                    "accuratepasses_per_90": 480.0,
                }
            ]
        )
        out, _ = analyze_match._apply_demo_v2_unit_policy(df, unit_policy="per_90")
        self.assertAlmostEqual(float(out.loc[0, "expected_goals"]), 1.65, places=6)
        self.assertAlmostEqual(float(out.loc[0, "goalsconceded"]), 0.95, places=6)

    def test_team_mapping_alias_resolution(self):
        df = pd.DataFrame(
            [
                {"team_name": "Brighton & Hove Albion"},
                {"team_name": "Arsenal"},
            ]
        )
        resolved, ctx = analyze_match._resolve_demo_team_name(df, "Brighton", team_col="team_name")
        self.assertEqual(resolved, "Brighton & Hove Albion")
        self.assertGreater(ctx.get("confidence", 0.0), 0.7)


if __name__ == "__main__":
    unittest.main()
