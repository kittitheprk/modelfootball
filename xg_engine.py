import pandas as pd
import os
import glob
import numpy as np

TEAM_ALIASES = {
    "Paris S-G": "Paris Saint-Germain",
    "PSG": "Paris Saint-Germain",
    "Rennes": "Stade Rennais",
    "Lyon": "Olympique Lyonnais",
    "Marseille": "Olympique de Marseille",
    "Monaco": "AS Monaco",
    "AS Monaco": "Monaco", # Fix for xG Engine linkage
    "Nice": "OGC Nice",
    "Lille": "LOSC Lille",
    "Brest": "Stade Brestois",
    "Stade Brestois": "Brest", 
    "Man Utd": "Manchester United",
    "Manchester Utd": "Manchester United",
    "Sheffield Utd": "Sheffield United",
    "Nott'm Forest": "Nottingham Forest",
    "Wolves": "Wolverhampton",
    "Brighton": "Brighton & Hove Albion",
    "Inter": "Internazionale",
    "Atletico Madrid": "Atletico Madrid",
    "Athletic Bilbao": "Athletic Club",
    "Real Betis": "Real Betis",
}

class XGEngine:
    def __init__(self, league_name="Premier_League"):
        self.base_dir = f"Match Logs/{league_name}"
        self.aliases = TEAM_ALIASES
        
    def get_team_rolling_stats(self, team_name, n_games=10):
        """
        Calculates rolling xG/xGA and Form (Last 5 games).
        """
        # Handle naming variations
        # 1. Check strict alias map first
        target_name = team_name
        if team_name in self.aliases:
            target_name = self.aliases[team_name]
        
        # 2. Try exact matches with target name (aliased or original)
        team_file = None
        # Try direct file with alias
        f_alias = os.path.join(self.base_dir, f"{target_name}.xlsx")
        if os.path.exists(f_alias):
            team_file = f_alias
        
        # 3. If not found, try common variations on both original and target
        if not team_file:
            variations = [target_name, team_name]
            # Add Utd/United variations
            extra = []
            for v in variations:
                extra.append(v.replace(" Utd", " United"))
                extra.append(v.replace(" United", " Utd"))
            
            all_vars = list(dict.fromkeys(variations + extra)) # unique
            
            for v in all_vars:
                f = os.path.join(self.base_dir, f"{v}.xlsx")
                if os.path.exists(f):
                    team_file = f
                    break
        
        # 2. Try case-insensitive and accent-insensitive matching
        if not team_file and os.path.exists(self.base_dir):
            import unicodedata
            def normalize(s):
                return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower()
            
            target_norm = normalize(team_name)
            for f in os.listdir(self.base_dir):
                if f.endswith(".xlsx"):
                    file_name = f.replace(".xlsx", "")
                    if normalize(file_name) == target_norm or target_norm in normalize(file_name):
                        team_file = os.path.join(self.base_dir, f)
                        break

        if not team_file:
            print(f"[XGEngine] Warning: Match logs not found for {team_name} in {self.base_dir}")
            return None

        try:
            # 1. Match Results & Form (Sheet 0)
            df_res = pd.read_excel(team_file, sheet_name=0)
            
            # Filter played matches (Result is not null)
            if 'Result' in df_res.columns:
                df_res = df_res[df_res['Result'].notna()].copy()
                
                # Sort by Date
                if 'Date' in df_res.columns:
                    df_res['Date'] = pd.to_datetime(df_res['Date'])
                    df_res = df_res.sort_values(by='Date', ascending=False)
                
                # Calculate Form (Last 5)
                recent_5 = df_res.head(5)
                points = 0
                for res in recent_5['Result']:
                    if str(res).startswith('W'): points += 3
                    elif str(res).startswith('D'): points += 1
                
                form_score = points # Max 15
            else:
                form_score = 7 # Default average
            
            # 2. Attack (Shooting Sheet)
            try:
                df_att = pd.read_excel(team_file, sheet_name='Shooting')
                if 'Standard_xG' in df_att.columns:
                    # Filter and Sort
                    if 'Date' in df_att.columns:
                        df_att['Date'] = pd.to_datetime(df_att['Date'])
                        df_att = df_att.sort_values(by='Date', ascending=False).head(n_games)
                    
                    avg_xg_for = df_att['Standard_xG'].mean()
                else:
                    avg_xg_for = 1.3
            except:
                # Fallback to Sheet 0 xG if Shooting not found
                if 'Expected_xG' in df_res.columns:
                     avg_xg_for = df_res.head(n_games)['Expected_xG'].mean()
                else:
                     avg_xg_for = 1.3

            # 3. Defense (Goalkeeping Sheet)
            try:
                df_def = pd.read_excel(team_file, sheet_name='Goalkeeping')
                # PSxG is the best xGA proxy
                if 'Performance_PSxG' in df_def.columns:
                    if 'Date' in df_def.columns:
                        df_def['Date'] = pd.to_datetime(df_def['Date'])
                        df_def = df_def.sort_values(by='Date', ascending=False).head(n_games)
                        
                    avg_xga = df_def['Performance_PSxG'].mean()
                    # If NaN, default
                    if pd.isna(avg_xga): avg_xga = 1.2
                else:
                    avg_xga = 1.2
            except:
                avg_xga = 1.2

            return {
                "team": team_name,
                "file_used": os.path.basename(team_file),
                "games_played": len(df_res),
                "form_last_5": form_score, # 0-15
                "attack": {
                    "xg_per_game": float(avg_xg_for) if not pd.isna(avg_xg_for) else 1.2,
                },
                "defense": {
                    "xga_per_game": float(avg_xga) if not pd.isna(avg_xga) else 1.2,
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
