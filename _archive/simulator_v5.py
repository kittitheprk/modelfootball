import numpy as np

def simulate_match(home_stats, away_stats, iterations=10000):
    """
    Monte Carlo Simulation v5.0 (xG Based)
    
    Logic:
    1. Predict Goal Expectancy (ExpG) based on Attack xG vs Defense xGA.
    2. Simulate match 10,000 times using Poisson distribution.
    3. Return probabilities and ranges.
    """
    
    # 1. Calculate Expected xG for this specific match
    # Home ExpG = (Home Attack xG + Away Defense xGA) / 2
    # Adjust for Home Advantage (approx +0.2 xG usually, or +10%)
    
    home_exp_xg = (home_stats['attack']['xg_per_game'] + away_stats['defense']['xga_per_game']) / 2 * 1.10
    away_exp_xg = (away_stats['attack']['xg_per_game'] + home_stats['defense']['xga_per_game']) / 2 * 0.90
    
    # 2. Monte Carlo Simulation
    home_goals_sim = np.random.poisson(home_exp_xg, iterations)
    away_goals_sim = np.random.poisson(away_exp_xg, iterations)
    
    # 3. Analyze Results
    home_wins = np.sum(home_goals_sim > away_goals_sim)
    draws = np.sum(home_goals_sim == away_goals_sim)
    away_wins = np.sum(home_goals_sim < away_goals_sim)
    
    home_win_prob = (home_wins / iterations) * 100
    draw_prob = (draws / iterations) * 100
    away_win_prob = (away_wins / iterations) * 100
    
    # Most likely score
    # Create pairs of (h, a)
    results = list(zip(home_goals_sim, away_goals_sim))
    from collections import Counter
    most_common = Counter(results).most_common(1)[0][0]
    
    return {
        "home_win_prob": home_win_prob,
        "draw_prob": draw_prob,
        "away_win_prob": away_win_prob,
        "expected_goals_home": home_exp_xg,
        "expected_goals_away": away_exp_xg,
        "most_likely_score": f"{most_common[0]}-{most_common[1]}"
    }

if __name__ == "__main__":
    # Dummy data for testing
    h_stats = {"attack": {"xg_per_game": 1.8}, "defense": {"xga_per_game": 1.2}}
    a_stats = {"attack": {"xg_per_game": 1.5}, "defense": {"xga_per_game": 1.5}}
    print(simulate_match(h_stats, a_stats))
