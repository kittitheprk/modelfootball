import numpy as np

class MatchSimulator:
    def __init__(self):
        pass

    def run_monte_carlo(self, lambda_home, lambda_away, n_sims=10000):
        """
        Runs a Monte Carlo simulation for the match.
        """
        # Generate random scores based on Poisson distribution
        home_goals_sim = np.random.poisson(lambda_home, n_sims)
        away_goals_sim = np.random.poisson(lambda_away, n_sims)
        
        # Determine outcomes
        home_wins = np.sum(home_goals_sim > away_goals_sim)
        draws = np.sum(home_goals_sim == away_goals_sim)
        away_wins = np.sum(home_goals_sim < away_goals_sim)
        
        # Calculate probabilities
        prob_home = home_wins / n_sims
        prob_draw = draws / n_sims
        prob_away = away_wins / n_sims
        
        # Most likely score (from simulation, though Poisson mode is analytic)
        # We can just return the analytic matrix from PoissonModel for score probs,
        # but simulation gives us a check.
        
        return {
            'home_win': prob_home,
            'draw': prob_draw,
            'away_win': prob_away
        }
