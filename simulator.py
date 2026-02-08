
import numpy as np

def simulate_match(home_team, away_team, home_stats, away_stats, league_stats, iterations=300):
    """
    Simulate a match 300 times using Poisson distribution based on xG or Goal stats.
    
    Args:
        home_team (str): Name of home team
        away_team (str): Name of away team
        home_stats (dict): {'goals_scored_per_game': float, 'goals_conceded_per_game': float}
        away_stats (dict): {'goals_scored_per_game': float, 'goals_conceded_per_game': float}
        league_stats (dict): {'avg_goals_home': float, 'avg_goals_away': float}
        iterations (int): Number of simulations (default 300)
        
    Returns:
        dict: Simulation results (probabilities, most likely score)
    """
    
    # Calculate Attack and Defense strengths
    # Home Attack Strength = Home Goals Scored / League Avg Home Goals
    home_att = home_stats['goals_scored_per_game'] / league_stats['avg_goals_home']
    # Away Defense Weakness = Away Goals Conceded / League Avg Home Goals (approx)
    away_def = away_stats['goals_conceded_per_game'] / league_stats['avg_goals_home']
    
    # Away Attack Strength
    away_att = away_stats['goals_scored_per_game'] / league_stats['avg_goals_away']
    # Home Defense Weakness
    home_def = home_stats['goals_conceded_per_game'] / league_stats['avg_goals_away']
    
    # Expected Goals
    home_exp_goals = home_att * away_def * league_stats['avg_goals_home']
    away_exp_goals = away_att * home_def * league_stats['avg_goals_away']
    
    # Run Simulation
    home_scores = np.random.poisson(home_exp_goals, iterations)
    away_scores = np.random.poisson(away_exp_goals, iterations)
    
    # Analyze Results
    home_wins = np.sum(home_scores > away_scores)
    draws = np.sum(home_scores == away_scores)
    away_wins = np.sum(home_scores < away_scores)
    
    # Most frequent scoreline
    scores_str = [f"{h}-{a}" for h, a in zip(home_scores, away_scores)]
    most_common_score = max(set(scores_str), key=scores_str.count)
    
    return {
        'iterations': iterations,
        'home_win_prob': (home_wins / iterations) * 100,
        'draw_prob': (draws / iterations) * 100,
        'away_win_prob': (away_wins / iterations) * 100,
        'most_likely_score': most_common_score,
        'home_exp_goals': home_exp_goals,
        'away_exp_goals': away_exp_goals
    }
