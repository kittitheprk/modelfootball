import pandas as pd
import os

files_to_check = {
    "all_stats": r"c:/Users/errig/OneDrive - มหาวิทยาลัยสยาม (1)/Desktop/model football/all stats/Premier_League_Stats.xlsx",
    "sofascore": r"c:/Users/errig/OneDrive - มหาวิทยาลัยสยาม (1)/Desktop/model football/sofascore_team_data/Premier_League_Team_Stats.xlsx",
    "match_logs": r"c:/Users/errig/OneDrive - มหาวิทยาลัยสยาม (1)/Desktop/model football/Match Logs/Premier_League/Arsenal.xlsx"
}

keywords = ["Pass", "Foul", "Interception", "Duel", "Tackle"]

for category, path in files_to_check.items():
    print(f"\n--- Checking {category} ({os.path.basename(path)}) ---")
    try:
        # Load the Excel file to get sheet names
        xls = pd.ExcelFile(path)
        print(f"Sheets: {xls.sheet_names}")
        
        # Check each sheet's headers
        for sheet in xls.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet, nrows=5) # Read only first few rows
            cols = df.columns.tolist()
            print(f"  Sheet '{sheet}' Columns:")
            found_cols = []
            for col in cols:
                # Check if any keyword key in column name (case insensitive)
                if any(k.lower() in str(col).lower() for k in keywords):
                   found_cols.append(str(col))
            
            if found_cols:
                print(f"    Found relevant columns: {found_cols}")
            else:
                print("    No relevant columns found in headers based on keywords.")

            # Also verify exact user requests if possible
            exact_matches = [c for c in cols if str(c) in ["Opponent Passes", "Fouls", "Interceptions", "Won Duels", "Sliding Tackles"]]
            if exact_matches:
                 print(f"    EXACT MATCHES found: {exact_matches}")

    except Exception as e:
        print(f"Error reading {path}: {e}")
