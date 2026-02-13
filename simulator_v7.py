import numpy as np
from collections import Counter

def simulate_match(home_xg, away_xg, home_sofascore=None, away_sofascore=None, iterations=10000):
    """
    Simulator v7.0 (Winner Mentality Edition)
    
    Changes from v6.0:
    1. Reduced Home/Away Factor: Home +6%, Away -4% (instead of +/- 15%)
    2. "Winner Mentality" (Superiority Bonus):
       - If a team is >15% stronger than opponent (based on xG/Goals), they get a +5% Execution Bonus.
       - This simulates "Big Teams" finding a way to win against smaller teams.
    
    Weights: xG 40% + Goals/90 60%
    """
    
    W_XG = 0.4    
    W_GOALS = 0.6 
    
    # Adjusted Home/Away Factor (User Feedback: -15% was too high)
    HOME_ADV = 1.06  # +6%
    AWAY_DIS = 0.96  # -4%
    
    # --- Calculate xG signal ---
    xg_home = (home_xg['attack']['xg_per_game'] + away_xg['defense']['xga_per_game']) / 2
    xg_away = (away_xg['attack']['xg_per_game'] + home_xg['defense']['xga_per_game']) / 2
    
    # --- Calculate Goals/90 signal ---
    if home_sofascore and away_sofascore:
        goals_home = (home_sofascore['goals_scored_per_game'] + away_sofascore['goals_conceded_per_game']) / 2
        goals_away = (away_sofascore['goals_scored_per_game'] + home_sofascore['goals_conceded_per_game']) / 2
    else:
        goals_home = xg_home
        goals_away = xg_away
        W_XG = 1.0
        W_GOALS = 0.0
    
    # --- Hybrid Expected Goals (Base) ---
    base_home = (W_XG * xg_home + W_GOALS * goals_home)
    base_away = (W_XG * xg_away + W_GOALS * goals_away)
    
    # --- "Winner Mentality" (Superiority Bonus) ---
    # Logic: If Team A is > 15% better than Team B, apply a "Finishing Bonus" of +5%
    # This reflects that top teams are more clinical and find ways to win.
    
    ratio_home = base_home / (base_away + 0.001)
    ratio_away = base_away / (base_home + 0.001)
    
    winner_bonus_home = 1.0
    winner_bonus_away = 1.0
    
    if ratio_home > 1.15: # Home is >15% better
        winner_bonus_home = 1.05 # +5% Bonus
    
    if ratio_away > 1.15: # Away is >15% better
        winner_bonus_away = 1.05 # +5% Bonus
        
    # Apply All Factors
    final_home = base_home * HOME_ADV * winner_bonus_home
    final_away = base_away * AWAY_DIS * winner_bonus_away
    
    # Safety
    final_home = max(final_home, 0.3)
    final_away = max(final_away, 0.3)
    
    # --- Monte Carlo Simulation ---
    home_goals_sim = np.random.poisson(final_home, iterations)
    away_goals_sim = np.random.poisson(final_away, iterations)
    
    # --- Analyze Results ---
    home_wins = np.sum(home_goals_sim > away_goals_sim)
    draws = np.sum(home_goals_sim == away_goals_sim)
    away_wins = np.sum(home_goals_sim < away_goals_sim)
    
    home_win_prob = (home_wins / iterations) * 100
    draw_prob = (draws / iterations) * 100
    away_win_prob = (away_wins / iterations) * 100
    
    # Most likely score
    results = list(zip(home_goals_sim, away_goals_sim))
    most_common = Counter(results).most_common(1)[0][0]
    
    # Top 3 scores
    top3 = Counter(results).most_common(3)
    top3_str = ", ".join([f"{s[0][0]}-{s[0][1]} ({s[1]/iterations*100:.1f}%)" for s in top3])
    
    return {
        "home_win_prob": home_win_prob,
        "draw_prob": draw_prob,
        "away_win_prob": away_win_prob,
        "expected_goals_home": final_home,
        "expected_goals_away": final_away,
        "most_likely_score": f"{most_common[0]}-{most_common[1]}",
        "top3_scores": top3_str,
        "base_exp_home": base_home, # For debug
        "base_exp_away": base_away, # For debug
        "bonus_applied": f"Home x{winner_bonus_home} | Away x{winner_bonus_away}"
    }


if __name__ == "__main__":
    # === BACKTEST against known matches ===
    print("=" * 60)
    print("SIMULATOR v7.0 (Winner Mentality) — BACKTEST RESULTS")
    print("=" * 60)
    
    test_matches = [
         {
            "name": "Roma vs Cagliari",
            "actual_result": "Home", "actual_score": "2-0",
            "h_xg": {"attack": {"xg_per_game": 1.8}, "defense": {"xga_per_game": 1.0}},
            "a_xg": {"attack": {"xg_per_game": 1.1}, "defense": {"xga_per_game": 1.6}},
            "h_ss": {"goals_scored_per_game": 1.9, "goals_conceded_per_game": 0.9},
            "a_ss": {"goals_scored_per_game": 1.0, "goals_conceded_per_game": 1.7},
        },
        {
            "name": "Tottenham vs Newcastle",
            "actual_result": "Away", "actual_score": "1-2",
            "h_xg": {"attack": {"xg_per_game": 1.6}, "defense": {"xga_per_game": 1.4}},
            "a_xg": {"attack": {"xg_per_game": 1.7}, "defense": {"xga_per_game": 1.1}},
            "h_ss": {"goals_scored_per_game": 1.5, "goals_conceded_per_game": 1.3},
            "a_ss": {"goals_scored_per_game": 1.8, "goals_conceded_per_game": 1.0},
        },
        {
            "name": "Everton vs Bournemouth",
            "actual_result": "Away", "actual_score": "1-2",
            "h_xg": {"attack": {"xg_per_game": 1.1}, "defense": {"xga_per_game": 1.3}},
            "a_xg": {"attack": {"xg_per_game": 1.6}, "defense": {"xga_per_game": 1.2}},
            "h_ss": {"goals_scored_per_game": 0.9, "goals_conceded_per_game": 1.4},
            "a_ss": {"goals_scored_per_game": 1.7, "goals_conceded_per_game": 1.1},
        },
        {
            "name": "Sunderland vs Liverpool",
            "actual_result": "Away", "actual_score": "0-1",
            "h_xg": {"attack": {"xg_per_game": 1.3}, "defense": {"xga_per_game": 1.2}},
            "a_xg": {"attack": {"xg_per_game": 1.7}, "defense": {"xga_per_game": 0.7}},
            "h_ss": {"goals_scored_per_game": 1.2, "goals_conceded_per_game": 1.3},
            "a_ss": {"goals_scored_per_game": 2.1, "goals_conceded_per_game": 0.6},
        },
    ]
    
    correct = 0
    for m in test_matches:
        sim = simulate_match(m["h_xg"], m["a_xg"], m["h_ss"], m["a_ss"])
        
        # Determine predicted result
        probs = {"Home": sim["home_win_prob"], "Draw": sim["draw_prob"], "Away": sim["away_win_prob"]}
        pred_result = max(probs, key=probs.get)
        is_correct = "OK" if pred_result == m["actual_result"] else "WRONG"
        if pred_result == m["actual_result"]:
            correct += 1
            
        print(f"\n{m['name']} (Actual: {m['actual_score']} {m['actual_result']})")
        print(f"  Predicted: {sim['most_likely_score']} {pred_result}")
        print(f"  Home {sim['home_win_prob']:.1f}% | Draw {sim['draw_prob']:.1f}% | Away {sim['away_win_prob']:.1f}%")
        print(f"  ExpG: Home {sim['expected_goals_home']:.2f} vs Away {sim['expected_goals_away']:.2f}")
        print(f"  Bonus: {sim['bonus_applied']}")
        print(f"  Result: {is_correct}")
    
    print(f"\n{'=' * 60}")
    print(f"ACCURACY: {correct}/{len(test_matches)} ({correct/len(test_matches)*100:.0f}%)")
    print(f"{'=' * 60}")
