
import pandas as pd
import os

file_path = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\prediction_tracker.xlsx"

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    exit()

try:
    df_pred = pd.read_excel(file_path, sheet_name="Predictions")
    df_bet = pd.read_excel(file_path, sheet_name="bet predic")

    matches = ["Girona", "Cagliari", "Lyon"]
    
    print("\n--- Predictions Sheet ---")
    for index, row in df_pred.iterrows():
        match = str(row.get("Match", ""))
        if any(m in match for m in matches):
            print(f"{row['Date']} | {match} | Score: {row.get('Actual_Score')} | Result: {row.get('Actual_Result')}")

    print("\n--- Bet Predic Sheet ---")
    for index, row in df_bet.iterrows():
        match = str(row.get("Match", ""))
        if any(m in match for m in matches):
            print(f"{row['Date']} | {match} | Bet: {row.get('Selected_Bet')} | Result: {row.get('Bet_Result')} | Score: {row.get('Actual_Score')}")

except Exception as e:
    print(f"Error: {e}")
