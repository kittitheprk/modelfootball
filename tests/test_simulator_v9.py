import os
import sys
import unittest

# Ensure we can import local modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import simulator_v9
import xg_engine


class TestSimulatorV9(unittest.TestCase):
    def test_player_aware_pipeline(self):
        league = "Premier_League"
        eng = xg_engine.XGEngine(league)

        home = "Arsenal"
        away = "Liverpool"

        h_xg = eng.get_team_rolling_stats(home, n_games=8)
        a_xg = eng.get_team_rolling_stats(away, n_games=8)

        self.assertIsNotNone(h_xg, "Could not fetch xG stats for home team")
        self.assertIsNotNone(a_xg, "Could not fetch xG stats for away team")

        context_text = """
        **Confirmed Lineups:**
        **Arsenal (4-3-3):**
        *   **GK:** David Raya
        *   **DEF:** Ben White, William Saliba, Gabriel Magalhaes, Oleksandr Zinchenko
        *   **MID:** Martin Odegaard, Declan Rice, Kai Havertz
        *   **FW:** Bukayo Saka, Gabriel Jesus, Gabriel Martinelli
        **Liverpool (4-3-3):**
        *   **GK:** Alisson
        *   **DEF:** Trent Alexander-Arnold, Ibrahima Konate, Virgil van Dijk, Andrew Robertson
        *   **MID:** Alexis Mac Allister, Dominik Szoboszlai, Ryan Gravenberch
        *   **FW:** Mohamed Salah, Darwin Nunez, Luis Diaz
        """

        sim = simulator_v9.simulate_match(
            h_xg,
            a_xg,
            None,
            None,
            iterations=1000,
            league=league,
            home_team=home,
            away_team=away,
            context_text=context_text,
        )

        self.assertEqual(sim.get("model_version"), "v9")
        self.assertIn("lineup_context", sim)
        self.assertIn("fatigue_context", sim)
        self.assertIn("progression_context", sim)
        self.assertIn("key_matchups", sim)
        self.assertIn("position_battles", sim)
        self.assertIn("math_winner_context", sim)

        total_prob = sim["home_win_prob"] + sim["draw_prob"] + sim["away_win_prob"]
        self.assertAlmostEqual(total_prob, 100.0, delta=0.2)

    def test_tactical_flow_adjustment(self):
        h_xg = {"attack": {"xg_per_game": 1.45}, "defense": {"xga_per_game": 1.10}, "form_last_5": 10}
        a_xg = {"attack": {"xg_per_game": 1.10}, "defense": {"xga_per_game": 1.35}, "form_last_5": 6}

        base = simulator_v9.simulate_match(h_xg, a_xg, None, None, iterations=1000)

        home_flow = {
            "calc_PPDA": 4.6,
            "calc_FieldTilt_Pct": 0.62,
            "calc_HighError_Rate": 19.0,
            "calc_Directness": 0.12,
            "calc_BigChance_Diff": 6.0,
        }
        away_flow = {
            "calc_PPDA": 11.8,
            "calc_FieldTilt_Pct": 0.39,
            "calc_HighError_Rate": 11.0,
            "calc_Directness": 0.07,
            "calc_BigChance_Diff": -6.0,
        }

        with_tactical = simulator_v9.simulate_match(
            h_xg,
            a_xg,
            None,
            None,
            iterations=1000,
            home_flow=home_flow,
            away_flow=away_flow,
        )

        tactical_ctx = with_tactical.get("tactical_context", {})
        self.assertTrue(tactical_ctx.get("enabled"))
        self.assertGreater(tactical_ctx.get("home_adjustment", 0.0), 0.0)
        self.assertLess(tactical_ctx.get("away_adjustment", 0.0), 0.0)
        self.assertGreater(with_tactical["expected_goals_home"], base["expected_goals_home"])
        self.assertLess(with_tactical["expected_goals_away"], base["expected_goals_away"])


if __name__ == "__main__":
    unittest.main()
