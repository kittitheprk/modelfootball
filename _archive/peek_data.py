import pandas as pd
import os
import sys

# Force utf-8 for stdout if possible, or just avoid printing complex chars
sys.stdout.reconfigure(encoding='utf-8')

def peek_excel(filepath, label):
    print(f"--- Peeking at {label} ---")
    try:
        xl = pd.ExcelFile(filepath)
        print(f"Sheet names: {xl.sheet_names}")
        # Read first sheet
        df = xl.parse(xl.sheet_names[0])
        print(f"First sheet columns: {df.columns.tolist()}")
        print(f"First sheet shape: {df.shape}")
        # print head but only few columns to avoid mess
        print(df.iloc[:3, :5].to_string())
    except Exception as e:
        print(f"Error reading {label}: {e}")

peek_excel(r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\sofascore_team_data\Bundesliga_Team_Stats.xlsx", "Bundesliga_Team_Stats")
peek_excel(r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\game flow\Bundesliga_GameFlow.xlsx", "Bundesliga_GameFlow")
