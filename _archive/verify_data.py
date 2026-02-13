
import pandas as pd
import os

def check_file(path, team_col, teams):
    print(f"\n--- Checking {path} ---")
    if not os.path.exists(path):
        print("FILE NOT FOUND")
        return

    try:
        df = pd.read_excel(path)
        for team in teams:
            # Fuzzy match
            row = df[df[team_col].str.contains(team, case=False, na=False)]
            if row.empty:
                print(f"{team}: NOT FOUND in {team_col}")
            else:
                print(f"{team}: Found")
                # Print key columns based on file type
                if "GameFlow" in path:
                    cols = ['Team_Name', 'calc_PPDA', 'calc_Directness', 'calc_FieldTilt_Pct']
                    print(row[cols].to_string(index=False))
                elif "all stats" in path:
                    cols = ['Squad', 'Poss', 'Per 90 Minutes_Gls', 'Per 90 Minutes_Ast']
                    print(row[cols].to_string(index=False))
                # sofaplayer handled differently usually, but let's see
    except Exception as e:
        print(f"Error: {e}")

def check_players(team):
    path = f"sofaplayer/Premier_League/{team}_stats.xlsx"
    print(f"\n--- Checking Player Stats for {team} ---")
    if not os.path.exists(path):
        print(f"File not found: {path}")
        # Try search
        base = "sofaplayer/Premier_League"
        for f in os.listdir(base):
            if team in f:
                path = os.path.join(base, f)
                print(f"Found alternative: {path}")
                break
    
    if os.path.exists(path):
        try:
            df = pd.read_excel(path)
            print(f"Top 3 Rated:")
            print(df[['Player_Name', 'rating']].sort_values(by='rating', ascending=False).head(3).to_string(index=False))
            print(f"Top 3 Scorers:")
            print(df[['Player_Name', 'goals']].sort_values(by='goals', ascending=False).head(3).to_string(index=False))
        except Exception as e:
            print(f"Error: {e}")

teams = ["Liverpool", "Manchester City"]

# 1. Game Flow
check_file('game flow/Premier_League_GameFlow.xlsx', 'Team_Name', teams)

# 2. All Stats
check_file('all stats/Premier_League_Stats.xlsx', 'Squad', teams)

# 3. Players
check_players("Liverpool")
check_players("Manchester City")
