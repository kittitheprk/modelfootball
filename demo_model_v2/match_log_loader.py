import pandas as pd
import os
import datetime
import re

class MatchLogLoader:
    def __init__(self, logs_root_dir):
        self.logs_root_dir = logs_root_dir
        self.leagues = ["Premier_League", "La_Liga", "Serie_A", "Bundesliga", "Ligue_1"]

    def find_team_log(self, team_name):
        """
        Searches for the team's Excel file in the known league directories.
        Returns the full path if found, else None.
        """
        # Dictionary to map some common name variations if needed
        # For now, just try direct match in all leagues
        for league in self.leagues:
            # Check for exact match
            path = os.path.join(self.logs_root_dir, league, f"{team_name}.xlsx")
            if os.path.exists(path):
                return path, league
            
            # Check for case-insensitive match
            try:
                files = os.listdir(os.path.join(self.logs_root_dir, league))
                for f in files:
                    if f.lower() == f"{team_name.lower()}.xlsx":
                        return os.path.join(self.logs_root_dir, league, f), league
            except FileNotFoundError:
                continue
                
        return None, None

    def load_match_log(self, team_name):
        """
        Loads the match log for a specific team.
        Returns a DataFrame with standardized columns: 
        ['Date', 'Opponent', 'GF', 'GA', 'xG', 'xGA', 'Comp']
        """
        filepath, league = self.find_team_log(team_name)
        if not filepath:
            # print(f"Warning: Match log not found for {team_name}")
            return None

        try:
            df = pd.read_excel(filepath)
            
            # Identify columns
            date_col = next((c for c in df.columns if 'Date' in c), None)
            gf_col = next((c for c in df.columns if c.endswith('_GF')), None)
            ga_col = next((c for c in df.columns if c.endswith('_GA')), None)
            opponent_col = next((c for c in df.columns if c.endswith('_Opponent')), None)
            venue_col = next((c for c in df.columns if c.endswith('_Venue')), None)
            
            # Stats for Synthetic xG
            shots_col = next((c for c in df.columns if 'Standard_Sh' in c and 'SoT' not in c), None) # 'Standard_Sh'
            sot_col = next((c for c in df.columns if 'Standard_SoT' in c and '%' not in c), None)   # 'Standard_SoT'

            if not date_col or not gf_col or not ga_col:
                return None

            # Standardize
            df_std = pd.DataFrame()
            df_std['Date'] = pd.to_datetime(df[date_col], errors='coerce')
            df_std['Opponent'] = df[opponent_col] if opponent_col else "Unknown"
            
            # Venue standardization
            if venue_col:
                df_std['Venue'] = df[venue_col].astype(str).str.strip()
            else:
                df_std['Venue'] = "Unknown"
            
            df_std['GF'] = pd.to_numeric(df[gf_col], errors='coerce').fillna(0)
            df_std['GA'] = pd.to_numeric(df[ga_col], errors='coerce').fillna(0)
            
            # Synthetic xG Calculation
            # If we have Shots and SoT:
            if shots_col and sot_col:
                shots = pd.to_numeric(df[shots_col], errors='coerce').fillna(0)
                sot = pd.to_numeric(df[sot_col], errors='coerce').fillna(0)
                # Simple model: SoT ~0.30 xG, Off-Target ~0.05 xG
                # Note: 'Standard_Sh' usually includes SoT. So Off-Target = Sh - SoT.
                off_target = (shots - sot).clip(lower=0)
                df_std['xG'] = (sot * 0.30) + (off_target * 0.05)
            else:
                # Fallback to Goals if no shot data
                df_std['xG'] = df_std['GF'] 
            
            # For xGA (Expected Goals Against), we don't have opponent's shot data in this file usually.
            # We only have 'For Team' stats.
            # So we have to use GA as the best proxy for xGA, or use a league average multiplier.
            # Let's use GA for now, but smooth it later.
            df_std['xGA'] = df_std['GA']

            # Filter valid outcomes (Played matches only)
            now = pd.Timestamp.now()
            df_std = df_std[df_std['Date'] < now].copy()
            df_std = df_std[df_std['GF'].notna()] # Ensure played
            
            # Sort by Date Descending
            df_std = df_std.sort_values(by='Date', ascending=False).reset_index(drop=True)
            
            return df_std

        except Exception as e:
            print(f"Error loading log for {team_name}: {e}")
            return None
