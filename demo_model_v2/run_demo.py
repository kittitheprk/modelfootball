import sys
import os
import pandas as pd
import numpy as np

# Add current directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_loader import DataLoader
from feature_engine import FeatureEngine
from match_log_loader import MatchLogLoader
from poisson_model import PoissonModel
from simulator import MatchSimulator

def main():
    print("=== Demo Model v2: Match Prediction Pipeline ===")
    
    # 1. Setup
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir) # Go up one level from 'demo_model_v2'
    data_folder = os.path.join(project_root, 'sofascore_team_data')
    match_logs_folder = os.path.join(project_root, 'Match Logs')
    
    print("Loading data from: [Project Data Folder]")
    loader = DataLoader(data_folder)
    log_loader = MatchLogLoader(match_logs_folder)
    
    # 2. User Input
    import argparse
    parser = argparse.ArgumentParser(description='Run Demo Model v2 Prediction')
    parser.add_argument('home', type=str, nargs='?', default="Arsenal", help='Home Team Name')
    parser.add_argument('away', type=str, nargs='?', default="Liverpool", help='Away Team Name')
    parser.add_argument('--league', type=str, default="All", help='League Name')
    parser.add_argument('--venue', type=str, choices=['Home', 'Away'], help="Force venue (optional)")
    parser.add_argument("--missing_home", type=str, help="Comma-separated missing home players")
    parser.add_argument("--missing_away", type=str, help="Comma-separated missing away players")
    
    args = parser.parse_args()
    
    home_team = args.home
    away_team = args.away
    league_name = args.league
    
    # 3. Load Data
    try:
        df = loader.load_data(league_name)
    except Exception as e:
        print(f"Error loading data for {league_name}: {e}")
        return
    
    # 4. Feature Engineering
    engine = FeatureEngine()
    df_processed = engine.calculate_feature_metrics(df)

    # 4b. Player Impact
    from player_impact_engine import PlayerImpactEngine
    impact_engine = PlayerImpactEngine(data_folder) # sofaplayer data is in 'sofascore_team_data'.. wait, no
    
    # Correction: 'sofascore_team_data' contains team stats. 'sofaplayer' contains player stats.
    # We need to point PlayerImpactEngine to 'sofaplayer'.
    player_stats_root = os.path.join(project_root, 'sofaplayer')
    impact_engine = PlayerImpactEngine(player_stats_root)
    
    home_tax = impact_engine.calculate_missing_tax(home_team, league_name, args.missing_home)
    away_tax = impact_engine.calculate_missing_tax(away_team, league_name, args.missing_away)
    
    if args.missing_home:
        print(f"Missing Home Players: {args.missing_home} -> Tax: {home_tax}")
    if args.missing_away:
        print(f"Missing Away Players: {args.missing_away} -> Tax: {away_tax}")

    print(f"\nAnalyzing Match: {home_team} (Home) vs {away_team} (Away)")
    
    # 5. Get Ratings (Time-Decay Weighted + Home/Away Specific + Player Tax)
    try:
        home_ratings = engine.get_team_ratings(df_processed, home_team, match_log_loader=log_loader, venue="Home", player_tax=home_tax)
        away_ratings = engine.get_team_ratings(df_processed, away_team, match_log_loader=log_loader, venue="Away", player_tax=away_tax)
    except ValueError as e:
        print(f"Error: {e}")
        return

    print(f"\n{home_team} Ratings ({home_ratings.get('source', 'Unknown')}): Attack={home_ratings['attack']:.2f}, Defense={home_ratings['defense']:.2f}")
    print(f"{away_team} Ratings ({away_ratings.get('source', 'Unknown')}): Attack={away_ratings['attack']:.2f}, Defense={away_ratings['defense']:.2f}")

    # 6. Poisson Model
    model = PoissonModel()
    
    # Calculate League Averages for scaling (Context)
    league_avg_home_goals = 1.6 # Approximation or calculate from data if available
    league_avg_away_goals = 1.2 # Approximation
    
    lambda_home, lambda_away = model.predict_match_lambdas(
        home_ratings, away_ratings, league_avg_home_goals, league_avg_away_goals
    )
    
    print(f"\nExpected Goals (xG):")
    print(f"{home_team}: {lambda_home:.2f}")
    print(f"{away_team}: {lambda_away:.2f}")
    
    # Score Matrix
    score_matrix = model.get_score_probability_matrix(lambda_home, lambda_away)
    
    # Heatmap Visualization
    print(f"\nScore Probability Heatmap (Rows: {home_team}, Cols: {away_team}):")
    print("      " + "  ".join([f"{j:<4}" for j in range(5)]))
    print("    " + "-" * 30)
    for i in range(5):
        row_str = f"{i:>2} | "
        for j in range(5):
            prob = score_matrix[i, j]
            if prob > 0.10: # Highlight high prob
                cell = f"\033[1m{prob:.0%}\033[0m" # Bold
            elif prob < 0.01:
                cell = "."
            else:
                cell = f"{prob:.0%}"
            row_str += f"{cell:<4}  "
        print(row_str)
    
    # Most likely score
    max_prob_idx = np.unravel_index(np.argmax(score_matrix), score_matrix.shape)
    print(f"\nMost Likely Score: {max_prob_idx[0]} - {max_prob_idx[1]} (Prob: {score_matrix[max_prob_idx]:.1%})")

    # 7. Simulation
    sim = MatchSimulator()
    
    results = sim.run_monte_carlo(lambda_home, lambda_away)
    
    print(f"\nWin Probabilities (10,000 Simulations):")
    print(f"{home_team} Win: {results['home_win']:.1%}")
    print(f"Draw: {results['draw']:.1%}")
    print(f"{away_team} Win: {results['away_win']:.1%}")
    
    # 8. Comparison with Implied Odds (Optional)
    print("\nImplied Fair Odds:")
    if results['home_win'] > 0:
        print(f"{home_team}: {1/results['home_win']:.2f}")
    if results['draw'] > 0:
        print(f"Draw: {1/results['draw']:.2f}")
    if results['away_win'] > 0:
        print(f"{away_team}: {1/results['away_win']:.2f}")

if __name__ == "__main__":
    main()
