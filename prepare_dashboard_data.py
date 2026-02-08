import pandas as pd
import json
import os
import numpy as np

# Base paths
BASE_DIR = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football"
SOFASCORE_DIR = os.path.join(BASE_DIR, "sofascore_team_data")
GAMEFLOW_DIR = os.path.join(BASE_DIR, "game flow")
ALL_STATS_DIR = os.path.join(BASE_DIR, "all stats")
OUTPUT_FILE = os.path.join(BASE_DIR, "dashboard", "data.json")

LEAGUES = {
    "Premier_League": "Premier League",
    "La_Liga": "La Liga",
    "Bundesliga": "Bundesliga",
    "Serie_A": "Serie A",
    "Ligue_1": "Ligue 1"
}

def load_team_data():
    all_teams = []
    
    for league_key, league_name in LEAGUES.items():
        print(f"Processing Team Data for {league_name}...")
        
        # 1. Load Game Flow (Calculated Metrics)
        gf_path = os.path.join(GAMEFLOW_DIR, f"{league_key}_GameFlow.xlsx")
        if os.path.exists(gf_path):
            gf_df = pd.read_excel(gf_path)
        else:
            print(f"  Warning: No Game Flow file found for {league_key}")
            gf_df = pd.DataFrame()

        # 2. Load SofaScore Stats
        ss_path = os.path.join(SOFASCORE_DIR, f"{league_key}_Team_Stats.xlsx")
        if os.path.exists(ss_path):
            ss_df = pd.read_excel(ss_path)
            # Normalize column names in SS DF (e.g. 'Team Name' -> 'Team')
            # ss_df columns likely: 'Team', 'Goals', ...
        else:
            print(f"  Warning: No SofaScore file found for {league_key}")
            ss_df = pd.DataFrame()

        # Merge
        # We need a common key. usually 'Team' or 'Team_Name'.
        # GF has 'Team_Name'. Let's check SS.
        
        merged_df = pd.DataFrame()
        
        if not ss_df.empty and 'Team' in ss_df.columns:
             ss_df = ss_df.rename(columns={'Team': 'Team_Name'})
        elif not ss_df.empty and 'name' in ss_df.columns:
             ss_df = ss_df.rename(columns={'name': 'Team_Name'})

        if not gf_df.empty and not ss_df.empty:
            # Fuzzy match or direct merge? Try direct first.
            merged_df = pd.merge(ss_df, gf_df, on='Team_Name', how='outer')
        elif not ss_df.empty:
            merged_df = ss_df
        elif not gf_df.empty:
            merged_df = gf_df
        
        if merged_df.empty:
            continue

        # Process columns
        for _, row in merged_df.iterrows():
            team_entry = {
                "id": hash(row.get('Team_Name', 'Unknown') + league_key) % 100000, # Simple dummy ID
                "name": row.get('Team_Name', 'Unknown'),
                "league": league_name,
                "metrics": {}
            }
            
            # Add all columns as metrics
            for col in merged_df.columns:
                if col in ['Team_Name', 'id']: continue
                val = row[col]
                # Clean keys: camelCase or snake_case
                clean_key = col.strip().replace(' ', '_').replace('.', '').replace('%', 'Pct')
                
                # Handle Numeric
                if pd.isna(val):
                    val = 0
                elif isinstance(val, (int, float)):
                    val = float(val)
                
                team_entry["metrics"][clean_key] = val
                
                # Mapping hacks for front-end compatibility
                # app.js looks for: averageBallPossession, tackles_per_90
                # If we have 'Ball possession', map it
                if clean_key.lower() == 'ball_possession':
                    team_entry["metrics"]['averageBallPossession'] = val
                if clean_key.lower() == 'tackles_per_game':
                     team_entry["metrics"]['tackles_per_90'] = val # Approximation if per 90 not avail
                
            all_teams.append(team_entry)

    return all_teams

def load_player_data():
    all_players = []
    
    # Sheets we want to merge
    SHEETS_OF_INTEREST = [
        'Player_Stats', 
        'Shooting', 
        'Passing', 
        'Possession', 
        'Defensive Actions', 
        'Goal and Shot Creation'
    ]
    
    for league_key, league_name in LEAGUES.items():
        print(f"Processing Player Data for {league_name}...")
        path = os.path.join(ALL_STATS_DIR, f"{league_key}_Stats.xlsx")
        
        if not os.path.exists(path):
            continue
            
        # Read all sheets
        data_frames = []
        xl = pd.ExcelFile(path)
        
        base_df = None
        
        for sheet in SHEETS_OF_INTEREST:
            if sheet not in xl.sheet_names:
                continue
            
            df = pd.read_excel(path, sheet_name=sheet)
            
            # Common keys for merging
            merge_keys = ['Player', 'Squad', 'Nation', 'Pos']
            # Filter to available keys
            merge_keys = [k for k in merge_keys if k in df.columns]
            
            if base_df is None:
                base_df = df
            else:
                # Drop columns that are already in base_df to avoid _x _y suffixes, except merge keys
                cols_to_use = merge_keys + [c for c in df.columns if c not in base_df.columns]
                base_df = pd.merge(base_df, df[cols_to_use], on=merge_keys, how='outer')

        if base_df is None or base_df.empty:
            continue

        # Calculate Percentiles for Radar Charts
        # We need to calc percentiles for specific metrics within Position/League context?
        # For simplicity, we calculate percentiles across the whole loaded dataset or per league.
        # Let's do it per league here for now.
        
        # Metrics to rank
        rank_metrics = [
            'Performance_Gls', 'Performance_Ast', 'Expected_xG', 'Expected_xAG',
            'Progression_PrgP', 'Progression_PrgC', 'Tackles_Tkl', 'Interceptions_Int',
            'Take-Ons_Succ', 'Touches_Touches', 'SCA_SCA', 'GCA_GCA'
        ]
        
        # Clean column names for usage
        # FBRef cols often have headers like 'Per 90 Minutes_Gls'.
        
        for _, row in base_df.iterrows():
            if pd.isna(row.get('Player')): continue
            
            player_entry = {
                "name": row.get('Player'),
                "squad": row.get('Squad'),
                "league": league_name,
                "position": row.get('Pos', 'Unknown'),
                "minutes90s": row.get('Playing Time_90s', 0),
                "metrics": {}
            }
            
            # Add all metrics
            for col in base_df.columns:
                if col in ['Player', 'Squad', 'Nation', 'Pos']: continue
                
                val = row[col]
                if pd.isna(val) or isinstance(val, str): continue
                
                # key cleaning
                key = col.replace(' ', '_').replace('+', '_plus_').replace('-', '_')
                
                player_entry["metrics"][key] = {
                    "raw": float(val),
                    "per90": float(val) / float(player_entry["minutes90s"]) if player_entry["minutes90s"] > 0 and 'Per 90' not in col else float(val)
                }
                
                # Mapping for app.js Radar
                # needed: Non_Penalty_Goals, Assists, Shot_Creating_Actions, Progressive_Passes, Successful_Take_Ons, Tackles
                
                # Extended Mapping for FBref Style Charts
                # Need: Non-Penalty Goals, npxG, Shots, Assists, xAG, npxG+xAG, SCA, GCA
                #       Passes Attempted, Pass %, Prog Passes, Prog Carries, Take-Ons, Touches (Att Pen)
                #       Tackles, Interceptions, Blocks, Clearances, Aerials Won
                
                simple_map = {
                    # Attacking
                    'Performance_G-PK': 'Non_Penalty_Goals',
                    'Expected_npxG': 'npxG',
                    'Standard_Sh': 'Shots_Total',
                    'Performance_Ast': 'Assists',
                    'Expected_xAG': 'xAG',
                    'Expected_npxG+xAG': 'npxG_plus_xAG',
                    'SCA_SCA': 'Shot_Creating_Actions',
                    
                    # Possession
                    'Total_Cmp': 'Passes_Completed', 
                    'Total_Att': 'Passes_Attempted', # usually Total_Att in Passing sheet
                    'Progression_PrgP': 'Progressive_Passes',
                    'Progression_PrgC': 'Progressive_Carries',
                    'Take_Ons_Succ': 'Successful_Take_Ons',
                    'Touches_Att 3rd': 'Touches_Att_3rd',
                    'Touches_Att Pen': 'Touches_Att_Pen',
                    
                    # Defending
                    'Tackles_Tkl': 'Tackles',
                    'Interceptions_Int': 'Interceptions',
                    'Blocks_Blocks': 'Blocks',
                    'Clearances_Clr': 'Clearances',
                    'Aerial_Duels_Won': 'Aerials_Won'
                }
                
                # Also check generically if key exists in df since sheet column names vary
                # e.g. 'Standard_Sh' might be 'Shots_Sh'
                if 'Shots_Sh' in row: simple_map['Shots_Sh'] = 'Shots_Total'
                if 'Total_Att' in row and sheet == 'Passing': simple_map['Total_Att'] = 'Passes_Attempted'
                
                if col in simple_map:
                    target = simple_map[col]
                    if target not in player_entry["metrics"]:
                         player_entry["metrics"][target] = {}
                    player_entry["metrics"][target]["raw"] = float(val)
                    if 'Per 90' not in col:
                        player_entry["metrics"][target]["per90"] = float(val) / player_entry["minutes90s"] if player_entry["minutes90s"] > 0 else 0
                    else:
                        player_entry["metrics"][target]["per90"] = float(val)

            all_players.append(player_entry)

    # Filter out players with low minutes (e.g., less than 90 minutes)
    MIN_MINUTES = 90
    filtered_players = []
    for p in all_players:
        if p['minutes90s'] * 90 >= MIN_MINUTES:
            filtered_players.append(p)
    all_players = filtered_players

    # Global Percentile Calculation (Merged players)
    
    # Full list of metrics for the extended radar chart
    calc_keys = [
        'Non_Penalty_Goals', 'npxG', 'Shots_Total', 'Assists', 'xAG', 'npxG_plus_xAG', 'Shot_Creating_Actions',
        'Passes_Attempted', 'Progressive_Passes', 'Progressive_Carries', 'Successful_Take_Ons', 'Touches_Att_Pen',
        'Tackles', 'Interceptions', 'Blocks', 'Clearances', 'Aerials_Won'
    ]
    
    # 1. Global Percentiles
    for key in calc_keys:
        values = []
        for p in all_players:
            if key in p['metrics'] and 'per90' in p['metrics'][key]:
                values.append(p['metrics'][key]['per90'])
        
        if not values: continue
        vals_array = np.array(values)
        
        for p in all_players:
            if key not in p['metrics']:
                 p['metrics'][key] = {'raw': 0, 'per90': 0, 'percentile': 0}
            
            if 'per90' in p['metrics'][key]:
                val = p['metrics'][key]['per90']
                p_rank = (vals_array < val).sum() / len(vals_array) * 100
                p['metrics'][key]['percentile'] = p_rank

    # 2. Positional Percentiles
    # Helper to simplify position
    def get_primary_pos(pos_str):
        if not isinstance(pos_str, str): return 'Unknown'
        return pos_str.split(',')[0] # e.g. "DF,MF" -> "DF"

    # Group players by position
    pos_groups = {}
    for p in all_players:
        pos = get_primary_pos(p['position'])
        if pos not in pos_groups: pos_groups[pos] = []
        pos_groups[pos].append(p)
        
    for pos, players_in_pos in pos_groups.items():
        if len(players_in_pos) < 10: continue # Skip tiny groups
        
        for key in calc_keys:
            # Gather values for this position group
            pos_values = []
            for p in players_in_pos:
                if key in p['metrics'] and 'per90' in p['metrics'][key]:
                    pos_values.append(p['metrics'][key]['per90'])
            
            if not pos_values: continue
            pos_vals_array = np.array(pos_values)
            
            # Calculate rank
            for p in players_in_pos:
                 if 'per90' in p['metrics'][key]:
                    val = p['metrics'][key]['per90']
                    # Rank within position
                    p_pos_rank = (pos_vals_array < val).sum() / len(pos_vals_array) * 100
                    p['metrics'][key]['pos_percentile'] = p_pos_rank

    return all_players

def main():
    print("Starting Data Pipeline...")
    
    teams = load_team_data()
    print(f"Loaded {len(teams)} teams.")
    
    players = load_player_data()
    print(f"Loaded {len(players)} players.")
    
    # Metadata
    metadata = {
        "leagues": list(LEAGUES.values()),
        "positions": ["GK", "DF", "MF", "FW"],
        "metrics": [] # We can verify usage later
    }
    
    full_data = {
        "metadata": metadata,
        "teams": teams,
        "players": players
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(full_data, f, default=str)

    print(f"Success! Data saved to dashboard/data.json")

if __name__ == "__main__":
    main()
