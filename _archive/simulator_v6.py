import numpy as np
from collections import Counter

def simulate_match(home_xg, away_xg, home_sofascore=None, away_sofascore=None, iterations=10000):
    """
    Simulator v6.0 (Hybrid Model)
    
    Combines:
    - xG data (Match Logs) = quality of chances created
    - Goals/Conceded per 90 (SofaScore) = actual outcomes
    
    Weights: xG 40% + Goals/90 60% (Goals/90 has proven more predictive)
    Home Advantage: +15% for home, -15% for away
    """
    
    W_XG = 0.4    # Weight for xG signal
    W_GOALS = 0.6 # Weight for Goals/90 signal
    HOME_ADV = 1.15
    AWAY_DIS = 0.85
    
    # --- Calculate xG signal ---
    xg_home = (home_xg['attack']['xg_per_game'] + away_xg['defense']['xga_per_game']) / 2
    xg_away = (away_xg['attack']['xg_per_game'] + home_xg['defense']['xga_per_game']) / 2
    
    # --- Calculate Goals/90 signal ---
    if home_sofascore and away_sofascore:
        goals_home = (home_sofascore['goals_scored_per_game'] + away_sofascore['goals_conceded_per_game']) / 2
        goals_away = (away_sofascore['goals_scored_per_game'] + home_sofascore['goals_conceded_per_game']) / 2
    else:
        # Fallback: use only xG if SofaScore data unavailable
        goals_home = xg_home
        goals_away = xg_away
        W_XG = 1.0
        W_GOALS = 0.0
    
    # --- Hybrid Expected Goals ---
    hybrid_home = (W_XG * xg_home + W_GOALS * goals_home) * HOME_ADV
    hybrid_away = (W_XG * xg_away + W_GOALS * goals_away) * AWAY_DIS
    
    # Safety: ensure positive values
    hybrid_home = max(hybrid_home, 0.3)
    hybrid_away = max(hybrid_away, 0.3)
    
    # --- Monte Carlo Simulation ---
    home_goals_sim = np.random.poisson(hybrid_home, iterations)
    away_goals_sim = np.random.poisson(hybrid_away, iterations)
    
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
        "expected_goals_home": hybrid_home,
        "expected_goals_away": hybrid_away,
        "most_likely_score": f"{most_common[0]}-{most_common[1]}",
        "top3_scores": top3_str,
        "data_sources": {
            "xg_home": xg_home,
            "xg_away": xg_away,
            "goals_home": goals_home if home_sofascore else None,
            "goals_away": goals_away if away_sofascore else None,
            "weight_xg": W_XG,
            "weight_goals": W_GOALS
        }
    }


if __name__ == "__main__":
    # === BACKTEST against known matches ===
    print("=" * 60)
    print("SIMULATOR v6.0 HYBRID — BACKTEST RESULTS")
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
        print(f"  Result: {is_correct}")
    
    print(f"\n{'=' * 60}")
    print(f"ACCURACY: {correct}/{len(test_matches)} ({correct/len(test_matches)*100:.0f}%)")
    print(f"{'=' * 60}")
