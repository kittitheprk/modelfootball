import pandas as pd
import os
import glob
import numpy as np

class XGEngine:
    def __init__(self, league_name="Premier_League"):
        self.base_dir = f"Match Logs/{league_name}"
        
    def get_team_rolling_stats(self, team_name, n_games=10):
        """
        Calculates rolling xG statistics for a team.
        Returns a dictionary with 'attack' and 'defense' metrics.
        """
        team_file = os.path.join(self.base_dir, f"{team_name}.xlsx")
        
        if not os.path.exists(team_file):
            print(f"[XGEngine] Warning: Match logs not found for {team_name}")
            return None

        try:
            # --- Attack Stats (Sheet 0 - Scores/Fixtures or similar) ---
            df_attack = pd.read_excel(team_file, sheet_name=0)
            
            # Filter valid matches
            if 'Expected_xG' in df_attack.columns:
                 df_attack = df_attack[df_attack['Expected_xG'].notna()].copy()
                 # Sort by Date descending
                 date_col = [c for c in df_attack.columns if 'Date' in c][0]
                 df_attack = df_attack.sort_values(by=date_col, ascending=False).head(n_games)
                 
                 avg_xg_for = df_attack['Expected_xG'].mean()
                 avg_shots_for = df_attack['Standard_Sh'].mean() if 'Standard_Sh' in df_attack.columns else 10.0
            else:
                 avg_xg_for = 1.2 # Default fallback
                 avg_shots_for = 10.0

            # --- Defense Stats (Goalkeeping Sheet) ---
            # Using PSxG (Post-Shot Expected Goals) as xGA proxy
            # This is available in the 'Goalkeeping' sheet
            try:
                df_defense = pd.read_excel(team_file, sheet_name='Goalkeeping')
                # Filter valid matches (columns might differ, check for PSxG)
                if 'Performance_PSxG' in df_defense.columns:
                    df_defense = df_defense[df_defense['Performance_PSxG'].notna()].copy()
                    
                    # Sort
                    date_col_def = [c for c in df_defense.columns if 'Date' in c][0]
                    df_defense = df_defense.sort_values(by=date_col_def, ascending=False).head(n_games)
                    
                    # PSxG is "Expected Goals based on shots on target".
                    # It's a good measure of "How many goals SHOULD the keeper have conceded?"
                    avg_xga = df_defense['Performance_PSxG'].mean()
                    
                    # If PSxG is NaN (e.g. no shots on target), fill with 0
                    if pd.isna(avg_xga): avg_xga = 0.5 
                    
                    # Scale up slightly because PSxG < xGA (ignores off-target shots)
                    # Heuristic: xGA approx PSxG * 1.2
                    avg_xga = avg_xga * 1.2
                    
                else:
                    avg_xga = 1.2 # Fallback
            except Exception as e:
                print(f"[XGEngine] Error reading Goalkeeping sheet: {e}")
                avg_xga = 1.2

            return {
                "team": team_name,
                "games_played": len(df_attack),
                "attack": {
                    "xg_per_game": avg_xg_for,
                    "shots_per_game": avg_shots_for,
                },
                "defense": {
                    "xga_per_game": avg_xga,
                }
            }

        except Exception as e:
            print(f"[XGEngine] Error processing {team_name}: {e}")
            return None

if __name__ == "__main__":
    # Test
    engine = XGEngine()
    stats = engine.get_team_rolling_stats("Sunderland", n_games=5)
    print(stats)
