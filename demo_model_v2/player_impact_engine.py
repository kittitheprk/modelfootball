import pandas as pd
import numpy as np
import os
import difflib

class PlayerImpactEngine:
    def __init__(self, data_root_dir):
        self.data_root_dir = data_root_dir

    def load_player_stats(self, team_name, league):
        """
        Loads player stats for a specific team.
        """
        # Filepath construction
        # Note: 'Premier_League' -> filename 'Arsenal_stats.xlsx'
        # The directory structure is 'sofaplayer/{League}/{Team}_stats.xlsx'
        
        # We need to handle team name variations. 
        # e.g., "Arsenal" -> "Arsenal_stats.xlsx"
        # "Aston Villa" -> "Aston Villa_stats.xlsx"
        
        filepath = os.path.join(self.data_root_dir, league, f"{team_name}_stats.xlsx")
        
        if not os.path.exists(filepath):
            # Try fuzzy match in directory?
            # For now, strict match or return None
            # print(f"Warning: Player stats not found for {team_name} in {league}")
            return None
            
        try:
            df = pd.read_excel(filepath)
            
            # Standardize columns
            # 'Player_Name' -> 'name'
            # 'totalRating' / 'countRating' -> 'rating'
            
            if 'Player_Name' in df.columns:
                df.rename(columns={'Player_Name': 'name'}, inplace=True)
            
            # Debug: available columns
            # print(f"DEBUG: Loaded columns for {team_name}: {df.columns.tolist()}")
                
            if 'totalRating' in df.columns and 'countRating' in df.columns:
                # Avoid division by zero
                df['rating'] = df['totalRating'] / df['countRating'].replace(0, 1)
            elif 'rating' in df.columns:
                pass # Already has rating
            else:
                print(f"Error: No rating columns found for {team_name}. Cols: {df.columns}")
                return None
                
            print(f"DEBUG: Loaded {len(df)} players for {team_name}. Sample: {df['name'].head(3).tolist()}")
            return df[['name', 'rating', 'position']].copy() if 'position' in df.columns else df[['name', 'rating']].copy()
            
        except Exception as e:
            print(f"Error loading player stats for {team_name}: {e}")
            return None

    def calculate_missing_tax(self, team_name, league, missing_players_str):
        """
        Calculates the reduction in team strength due to missing players.
        missing_players_str: Comma-separated string of player names (e.g., "Saka, Rice")
        Returns: {'attack_tax': float, 'defense_tax': float}
        """
        if not missing_players_str:
            return {'attack_tax': 1.0, 'defense_tax': 1.0}
            
        df = self.load_player_stats(team_name, league)
        if df is None or df.empty:
            return {'attack_tax': 1.0, 'defense_tax': 1.0}
            
        # Parse missing players
        missing_names_raw = [s.strip() for s in missing_players_str.split(',')]
        
        missing_indices = []
        df['name_lower'] = df['name'].str.lower()
        
        for raw_name in missing_names_raw:
            raw_lower = raw_name.lower()
            found = False
            
            # 1. Exact or Substring Match (Case Insensitive)
            # Check if input 'saka' is in 'bukayo saka'
            for idx, row in df.iterrows():
                if raw_lower in row['name_lower']:
                    missing_indices.append(idx)
                    found = True
                    # Break or continue? If 'Gabriel' is input, might match 'Gabriel Jesus' and 'Gabriel Magalhaes'.
                    # For safety, let's take the first match for now or highest rating?
                    # Let's take the first match and break to avoid double counting.
                    break 
            
            # 2. Fuzzy Match if strict/substring failed
            if not found:
                 match = difflib.get_close_matches(raw_lower, df['name_lower'], n=1, cutoff=0.6)
                 if match:
                     idx = df[df['name_lower'] == match[0]].index[0]
                     missing_indices.append(idx)
                     found = True
        
        if not missing_indices:
            print(f"DEBUG: No matching players found for input: {missing_players_str}")
            return {'attack_tax': 1.0, 'defense_tax': 1.0}
            
        # Impact Calculation Logic
        # 1. Identify "Starter Strength" (Avg rating of Top 11)
        # 2. Identify "Replacement Strength" (Avg rating of Next 5)
        
        df_sorted = df.sort_values(by='rating', ascending=False).reset_index(drop=True)
        top_11 = df_sorted.head(11)
        subs = df_sorted.iloc[11:16]
        
        avg_starter_rating = top_11['rating'].mean()
        avg_sub_rating = subs['rating'].mean() if not subs.empty else avg_starter_rating * 0.8
        
        # Calculate Tax
        # For every missing starter, we replace them with a generic 'sub'.
        # Tax = (Starter_Rating - Sub_Rating) * Weight
        
        total_rating_loss = 0
        
        for idx in missing_indices:
            # Find the row in df_sorted corresponding to original idx?
            # No, idx is index in original df. 
            player_rating = df.loc[idx, 'rating']
            
            # Check if this player is actually a starter (stats-wise)
            # Compare to the 11th best player (threshold)
            threshold_rating = df_sorted.iloc[10]['rating'] if len(df_sorted) > 10 else 0
            
            if player_rating >= threshold_rating: # Is in Top 11 range
                 rating_diff = player_rating - avg_sub_rating
                 if rating_diff > 0:
                     total_rating_loss += rating_diff
            else:
                pass # Player below threshold (Not a starter)
        
        # Scaling the tax
        # A loss of 1.0 total rating points (e.g., Saka 8.0 -> Sub 7.0) is huge.
        # Team avg rating is ~7.0.
        # A drop from 7.0 to 6.9 is significant in elo/power terms.
        # Let's say 1.0 cumulative rating loss = 10% performance drop.
        
        performance_drop = total_rating_loss * 0.10
        
        # Apply to both for now (simplicity), or split if we knew positions
        # Since we didn't check 'position' column thoroughly, broad tax is safer.
        tax = max(0.5, 1.0 - performance_drop) # Cap at 50% drop
        
        return {
            'attack_tax': tax,
            'defense_tax': tax 
        }
