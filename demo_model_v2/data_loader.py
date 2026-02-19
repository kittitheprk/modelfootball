import pandas as pd
import numpy as np
import os

class DataLoader:
    def __init__(self, data_folder):
        self.data_folder = data_folder

    def load_data(self, league_name):
        """
        Loads team stats from Excel.
        Expected filename format: '{league_name}_Team_Stats.xlsx'
        If league_name is 'All', loads all available league files.
        """
        if league_name == "All":
            all_dfs = []
            # List of known leagues or scan directory
            known_leagues = ["Premier_League", "La_Liga", "Serie_A", "Bundesliga", "Ligue_1"]
            for league in known_leagues:
                try:
                    df = self.load_data(league)
                    df['league_source'] = league
                    all_dfs.append(df)
                except FileNotFoundError:
                    continue
            
            if not all_dfs:
                raise FileNotFoundError("No league data found.")
            
            return pd.concat(all_dfs, ignore_index=True)

        filename = f"{league_name}_Team_Stats.xlsx"
        filepath = os.path.join(self.data_folder, filename)
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Data file not found: {filepath}")
        
        df = pd.read_excel(filepath)
        df = self._clean_column_names(df)
        df = self._impute_synthetic_xg(df)
        return df

    def _clean_column_names(self, df):
        """Standardizes column names to be snake_case."""
        df.columns = [c.replace(' ', '_').replace('/', '_').lower() for c in df.columns]
        return df

    def _impute_synthetic_xg(self, df):
        """
        Imputes 'expected_goals' (xG) if missing.
        Formula: xG ~ (0.1 * Shots) + (0.4 * Big Chances) + (0.75 * Penalty Goals)
        
        This is a heuristic approximation for demo purposes.
        Opta defines Big Chances as situations where a player should reasonably be expected to score.
        """
        # Feature Engineering: Synthetic xG
        if 'expected_goals' not in df.columns:
            # Check for required columns
            required = ['shots', 'bigchances']
            available = [c for c in required if c in df.columns]
            
            if len(available) == len(required):
                # Basic synthetic xG
                # Shots have avg xG ~0.10, Big Chances ~0.40
                # Overlap: BigChances are also Shots, so we split the weight
                # Non-BigChance Shots ~0.07, BigChance ~0.45
                
                # Let's use a simplified weighted sum for the demo
                shots = df['shots'].fillna(0)
                big_chances = df['bigchances'].fillna(0)
                penalties = df.get('penaltygoals', pd.Series(0, index=df.index)).fillna(0)
                
                # Formula:
                # xG = (Non-BigChance Shots * 0.07) + (Big Chances * 0.45) + (Penalties * 0.79)
                # Note: 'shots' includes big chances, so we subtract big_chances from total shots for the first term
                non_big_chance_shots = shots - big_chances
                non_big_chance_shots = non_big_chance_shots.apply(lambda x: max(x, 0)) # Ensure no negative
                
                synthetic_xg = (non_big_chance_shots * 0.07) + (big_chances * 0.45) 
                
                # Add penalties if available (xG of penalty is ~0.76-0.79)
                synthetic_xg += (penalties * 0.79)
                
                df['expected_goals_synthetic'] = synthetic_xg
                # Use synthetic as primary if missing
                df['expected_goals'] = synthetic_xg
                print("Generated synthetic xG based on Shots & Big Chances.")
            else:
                print(f"Warning: Missing columns for synthetic xG. Available: {available}")
                df['expected_goals'] = df['goals_scored'] # Fallback to actual goals
        
        # Defense Strength Proxy (xGA - Expected Goals Against)
        # If we don't have xGA, we can approximate it from Goals Conceded vs League Avg,
        # or if we have 'shots against' stats (check columns later).
        # For now, let's look for 'shots_against' or similar in the dataset in FeatureEngine.
        
        return df
