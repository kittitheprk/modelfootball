import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
import os
from data_loader import DataLoader
from feature_engine import FeatureEngine
from match_log_loader import MatchLogLoader
from poisson_model import PoissonModel
from simulator import MatchSimulator

def visualize_match(home_team, away_team, league):
    print(f"Visualizing: {home_team} vs {away_team} ({league})")
    
    # 1. Initialize
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir) # up one level
    
    # Paths
    # DataLoader expects 'data_folder', and load_data expects 'league_name'
    season_stats_dir = os.path.join(project_root, "sofascore_team_data")
    logs_dir = os.path.join(project_root, "Match Logs")
    output_dir = os.path.join(project_root, "analyses", "images")
    os.makedirs(output_dir, exist_ok=True)
    
    # 2. Load Data
    loader = DataLoader(season_stats_dir)
    try:
        df = loader.load_data(league)
    except FileNotFoundError:
        print(f"Error: Could not load data for league '{league}' in {season_stats_dir}")
        return
    
    log_loader = MatchLogLoader(logs_dir)
    engine = FeatureEngine()
    
    # 3. Process
    df_processed = engine.calculate_feature_metrics(df)
    
    # 4. Get Ratings (Dynamic Home/Away)
    try:
        home_ratings = engine.get_team_ratings(df_processed, home_team, match_log_loader=log_loader, venue="Home")
        away_ratings = engine.get_team_ratings(df_processed, away_team, match_log_loader=log_loader, venue="Away")
    except ValueError as e:
        print(f"Error: {e}")
        return

    # 5. Model Prediction
    model = PoissonModel()
    lambdas = model.predict_match_lambdas(
        home_ratings, 
        away_ratings, 
        league_avg_home_goals=1.5, 
        league_avg_away_goals=1.2
    )
    lambda_home, lambda_away = lambdas
    
    score_matrix = model.get_score_probability_matrix(lambda_home, lambda_away)
    
    # 6. Simulation (for Win Probs)
    sim = MatchSimulator()
    sim_results = sim.run_monte_carlo(lambda_home, lambda_away)
    
    # ==========================================
    # Visualization
    # ==========================================
    sns.set_theme(style="whitegrid")
    fig = plt.figure(figsize=(14, 6))
    fig.suptitle(f"Match Analysis: {home_team} vs {away_team}", fontsize=16, fontweight='bold')
    
    # Subplot 1: Score Heatmap
    ax1 = fig.add_subplot(1, 2, 1)
    
    # Limit matrix to 5x5 for readability in chart
    display_matrix = score_matrix[:5, :5]
    
    sns.heatmap(display_matrix, annot=True, fmt=".1%", cmap="YlGnBu", cbar=False, ax=ax1,
                xticklabels=range(5), yticklabels=range(5))
    
    ax1.set_title("Scoreline Probabilities")
    ax1.set_xlabel(f"{away_team} Goals")
    ax1.set_ylabel(f"{home_team} Goals")
    
    # Subplot 2: Win Probabilities
    ax2 = fig.add_subplot(1, 2, 2)
    
    outcomes = ['Home Win', 'Draw', 'Away Win']
    probs = [sim_results['home_win'], sim_results['draw'], sim_results['away_win']]
    colors = ['#1f77b4', '#7f7f7f', '#ff7f0e'] # Blue, Gray, Orange
    
    bars = ax2.bar(outcomes, probs, color=colors)
    ax2.set_ylim(0, 1.0)
    ax2.set_title("Match Outcome Probabilities (10,000 Sims)")
    ax2.set_ylabel("Probability")
    
    # Add labels on bars
    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height + 0.02,
                 f'{height:.1%}',
                 ha='center', va='bottom', fontsize=12, fontweight='bold')
        
    # Add Text Stats
    stats_text = (
        f"Team Ratings:\n"
        f"{home_team}: Att {home_ratings['attack']:.2f}, Def {home_ratings['defense']:.2f}\n"
        f"{away_team}: Att {away_ratings['attack']:.2f}, Def {away_ratings['defense']:.2f}\n\n"
        f"Expected Goals (xG):\n"
        f"{home_team}: {lambda_home:.2f}\n"
        f"{away_team}: {lambda_away:.2f}"
    )
    # Place text in empty space or bottom
    plt.figtext(0.5, 0.02, stats_text, ha="center", fontsize=10, bbox={"facecolor":"orange", "alpha":0.2, "pad":5})
    
    plt.tight_layout(rect=[0, 0.05, 1, 0.95]) # Make room for suptitle and bottom text
    
    # Save
    filename = f"{home_team}_vs_{away_team}.png".replace(" ", "_")
    save_path = os.path.join(output_dir, filename)
    plt.savefig(save_path, dpi=100)
    print(f"Visualization saved to: {filename}")
    plt.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize Match Predictions")
    parser.add_argument("home_team", type=str)
    parser.add_argument("away_team", type=str)
    parser.add_argument("--league", type=str, default="Premier_League")
    
    args = parser.parse_args()
    
    visualize_match(args.home_team, args.away_team, args.league)
