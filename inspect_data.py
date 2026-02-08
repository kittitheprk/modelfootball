
import pandas as pd
import os

base_path = r"c:/Users/errig/OneDrive - มหาวิทยาลัยสยาม (1)/Desktop/model football"
all_stats_path = os.path.join(base_path, "all stats", "Bundesliga_Stats.xlsx")
sofascore_path = os.path.join(base_path, "sofascore_team_data", "Bundesliga_Team_Stats.xlsx")

def inspect_excel(path, name):
    print(f"\n--- Inspecting {name} ---")
    try:
        xls = pd.ExcelFile(path)
        print(f"Sheet names: {xls.sheet_names}")
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet, nrows=5)
            print(f"\nSheet: {sheet}")
            print("Columns:", list(df.columns))
            # print("Sample Data:\n", df.head(1).to_string())
    except Exception as e:
        print(f"Error reading {name}: {e}")

inspect_excel(all_stats_path, "All Stats (Player/Team?)")
inspect_excel(sofascore_path, "Sofascore Team Data")
