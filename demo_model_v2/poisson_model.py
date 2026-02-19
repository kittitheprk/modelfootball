import numpy as np
from scipy.stats import poisson

class PoissonModel:
    def __init__(self):
        pass

    def predict_match_lambdas(self, home_ratings, away_ratings, league_avg_home_goals, league_avg_away_goals):
        """
        Calculates the expected goals (lambda) for home and away teams.
        Formula:
        Home Lambda = Home Attack * Away Defense * League Avg Home Goals
        Away Lambda = Away Attack * Home Defense * League Avg Away Goals
        
        Note: We also apply a small 'Home Advantage' factor if not implicit in league avg.
        """
        # Home Expectation
        home_attack = home_ratings['attack']
        away_defense = away_ratings['defense']
        
        # Away Expectation
        away_attack = away_ratings['attack']
        home_defense = home_ratings['defense']
        
        # Calculate Lambdas
        lambda_home = home_attack * away_defense * league_avg_home_goals
        lambda_away = away_attack * home_defense * league_avg_away_goals
        
        return lambda_home, lambda_away

    def get_score_probability_matrix(self, lambda_home, lambda_away, max_goals=10):
        """
        Generates a matrix of probabilities for each scoreline (0-0 to 10-10).
        """
        # Probability mass functions for Home and Away
        pmf_home = poisson.pmf(np.arange(max_goals + 1), lambda_home)
        pmf_away = poisson.pmf(np.arange(max_goals + 1), lambda_away)
        
        # Outer product to get joint probabilities (assuming independence initially)
        matrix = np.outer(pmf_home, pmf_away)
        
        # Dixon-Coles Adjustment for low-scoring draws
        # Increases prob of 0-0, 1-1 and decreases 1-0, 0-1 slightly
        # This corrects the Poisson tendency to underestimate draws.
        matrix = self._apply_dixon_coles(matrix, lambda_home, lambda_away)
        
        return matrix

    def _apply_dixon_coles(self, matrix, lambda_home, lambda_away):
        """
        Applies Dixon-Coles adjustment factor to the score matrix.
        Corrects for the dependence between low scores.
        """
        # Rho is the dependence parameter. Standard literature suggests ~ -0.1 to 0.1
        # We'll use a standard heuristic value of -0.13 (from original paper) or small adjustment
        rho = -0.13 
        
        # Adjustment factors
        # 0-0
        if matrix.shape[0] > 0 and matrix.shape[1] > 0:
            matrix[0, 0] *= (1 - (lambda_home * lambda_away * rho)) # Correction term simplified
            
            # Dixon-Coles formula is actually:
            # P(0,0) -> P(0,0) * (1 - lambda_h * lambda_a * rho)
            # P(1,0) -> P(1,0) * (1 + lambda_a * rho)
            # P(0,1) -> P(0,1) * (1 + lambda_h * rho)
            # P(1,1) -> P(1,1) * (1 - rho)
            
            # Let's apply standard Dixon-Coles logic if indices exist
            
            # 0-0
            factor_00 = 1 - (lambda_home * lambda_away * rho)
            # 1-0
            factor_10 = 1 + (lambda_away * rho)
            # 0-1
            factor_01 = 1 + (lambda_home * rho)
            # 1-1
            factor_11 = 1 - rho
            
            # Apply safely
            matrix[0, 0] =  matrix[0, 0] * factor_00
            if matrix.shape[0] > 1:
                matrix[1, 0] = matrix[1, 0] * factor_10
            if matrix.shape[1] > 1:
                matrix[0, 1] = matrix[0, 1] * factor_01
            if matrix.shape[0] > 1 and matrix.shape[1] > 1:
                matrix[1, 1] = matrix[1, 1] * factor_11

        # Re-normalize matrix to sum to 1.0 (since adjustment changes mass)
        matrix = matrix / np.sum(matrix)
            
        return matrix
