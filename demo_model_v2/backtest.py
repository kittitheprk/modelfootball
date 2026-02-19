import pandas as pd
import numpy as np
import os
import sys

# Ensure we can import from local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_loader import DataLoader
from feature_engine import FeatureEngine
from match_log_loader import MatchLogLoader
from poisson_model import PoissonModel
from simulator import MatchSimulator

def get_result_outcome(home_goals, away_goals):
    if home_goals > away_goals:
        return "Home"
    elif away_goals > home_goals:
        return "Away"
    else:
        return "Draw"

def main():
    print("=== Backtesting Demo Model v2 (Time-Decay) ===")
    
    # Paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)
    tracker_path = os.path.join(project_root, 'prediction_tracker.xlsx')
    data_folder = os.path.join(project_root, 'sofascore_team_data')
    match_logs_folder = os.path.join(project_root, 'Match Logs')
    
    # Load Tracker
    if not os.path.exists(tracker_path):
        print(f"Error: Tracker not found at {tracker_path}")
        return
        
    df_tracker = pd.read_excel(tracker_path)
    
    # Filter for matches with actual results
    if 'Actual_Score' not in df_tracker.columns:
        print("Error: 'Actual_Score' column not found.")
        return

    df_backtest = df_tracker[df_tracker['Actual_Score'].notna()].copy()
    print(f"Found {len(df_backtest)} completed matches to test.")

    # Initialize Model Components
    loader = DataLoader(data_folder)
    log_loader = MatchLogLoader(match_logs_folder)
    
    try:
        df_stats = loader.load_data("All")
    except Exception as e:
        print(f"Error loading stats: {e}")
        return
        
    engine = FeatureEngine()
    df_processed = engine.calculate_feature_metrics(df_stats)
    model = PoissonModel()
    
    correct_result = 0
    correct_score = 0
    total = 0
    brier_scores = []
    
    print(f"\n{'Match':<40} | {'Pred':<10} | {'Actual':<10} | {'Res?':<5} | {'Scr?':<5} | {'Source':<10} | {'Brier':<6}")
    print("-" * 115)

    for index, row in df_backtest.iterrows():
        home_team = row['Home_Team']
        away_team = row['Away_Team']
        actual_score_str = str(row['Actual_Score'])
        
        # Parse actual score
        try:
            parts = actual_score_str.split('-')
            actual_h = int(parts[0])
            actual_a = int(parts[1])
            actual_outcome = get_result_outcome(actual_h, actual_a)
        except:
            continue

        # Run Prediction
        try:
            # Pass log_loader and venue to get time-decay + home/away ratings
            home_ratings = engine.get_team_ratings(df_processed, home_team, match_log_loader=log_loader, venue="Home")
            away_ratings = engine.get_team_ratings(df_processed, away_team, match_log_loader=log_loader, venue="Away")
            
            source_h = home_ratings.get('source', 'Avg')
            source_a = away_ratings.get('source', 'Avg')
            source_str = "Decay" if "Weighted" in source_h else "Avg"
            
            lambda_h, lambda_a = model.predict_match_lambdas(
                home_ratings, away_ratings, 1.6, 1.2
            )
            
            score_matrix = model.get_score_probability_matrix(lambda_h, lambda_a)
            idx = np.unravel_index(np.argmax(score_matrix), score_matrix.shape)
            pred_h, pred_a = idx[0], idx[1]
            pred_outcome = get_result_outcome(pred_h, pred_a)
            
            is_correct_result = (pred_outcome == actual_outcome)
            is_correct_score = (pred_h == actual_h and pred_a == actual_a)
            
            if is_correct_result: correct_result += 1
            if is_correct_score: correct_score += 1
            total += 1
            
            res_mark = "YES" if is_correct_result else "NO"
            scr_mark = "YES" if is_correct_score else "NO"
            
            # Brier Score Calculation
            # Outcome Vector: Home=0, Draw=1, Away=2
            # Actual Outcome:
            actual_idx = 0 if actual_outcome == "Home" else (1 if actual_outcome == "Draw" else 2)
            
            # Probabilities from Simulation (Result Probs) are better than raw Poisson for match outcome
            # But here we used Poisson Matrix for Score. Let's run Sim briefly or derive from matrix.
            # Deriving from Matrix is faster:
            prob_home = np.sum(np.tril(score_matrix, -1))
            prob_draw = np.sum(np.diag(score_matrix))
            prob_away = np.sum(np.triu(score_matrix, 1))
            
            # Brier Score Formula: Sum((Prob_i - Outcome_i)^2)
            # Outcome_i is 1 if it happened, 0 if not.
            bs = (prob_home - (1 if actual_idx==0 else 0))**2 + \
                 (prob_draw - (1 if actual_idx==1 else 0))**2 + \
                 (prob_away - (1 if actual_idx==2 else 0))**2
                 
            brier_scores.append(bs)
            
            match_str = f"{home_team} vs {away_team}"
            print(f"{match_str:<40} | {pred_h}-{pred_a:<7} | {actual_h}-{actual_a:<7} | {res_mark:<5} | {scr_mark:<5} | {source_str:<10} | {bs:.3f}")
            
        except ValueError:
            pass
            
    print("-" * 115)
    print(f"Total Tested: {total}")
    if total > 0:
        print(f"Correct Result (W/D/L): {correct_result} ({correct_result/total:.1%})")
        print(f"Correct Exact Score:    {correct_score} ({correct_score/total:.1%})")
        print(f"Average Brier Score:    {np.mean(brier_scores):.4f} (Lower is better)")
    else:
        print("No matches matched.")

if __name__ == "__main__":
    main()
