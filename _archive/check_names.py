
import pandas as pd
import os

base_path = r"c:/Users/errig/OneDrive - มหาวิทยาลัยสยาม (1)/Desktop/model football"
all_stats_path = os.path.join(base_path, "all stats", "Bundesliga_Stats.xlsx")
sofascore_path = os.path.join(base_path, "sofascore_team_data", "Bundesliga_Team_Stats.xlsx")

def check_names():
    # Check Sofascore
    try:
        df_sofa = pd.read_excel(sofascore_path)
        print("Sofascore Teams:", df_sofa['Team_Name'].unique())
    except Exception as e:
        print("Error reading Sofascore:", e)
    
    # Check All Stats (Fbref)
    try:
        df_fbref = pd.read_excel(all_stats_path, sheet_name="Standard Stats") # "Standard Stats" might not exist, checking "Player_Stats" based on previous output which said "Player_Stats"
        # Wait, the previous output showed "Player_Stats" as the first sheet. Let's use that.
        # Actually it showed "Player_Stats" but also "Shooting", "Passing" etc.
        # I'll check "Player_Stats" for the 'Squad' column.
    except:
        pass
        
    try:
        df_fbref = pd.read_excel(all_stats_path, sheet_name="Player_Stats")
        print("Fbref Teams (Player_Stats):", df_fbref['Squad'].unique())
    except Exception as e:
        print("Error reading Fbref:", e)

check_names()
