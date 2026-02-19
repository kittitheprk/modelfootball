
import pandas as pd
import os

file_path = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\prediction_tracker.xlsx"

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    exit()

try:
    xl = pd.ExcelFile(file_path)
    sheets = {sheet: pd.read_excel(file_path, sheet_name=sheet) for sheet in xl.sheet_names}
    
    df_pred = sheets.get("Predictions")
    if df_pred is None:
        print("Predictions sheet not found.")
        exit()

    # Define updates: (Match Name substring, Date substring, Score, Result)
    # Result: 'Home', 'Away', 'Draw'
    updates = [
        ("Girona", "Barcelona", "2026-02-16", "2-1", "Home"),
        ("Cagliari", "Lecce", "2026-02-16", "0-2", "Away"),
        ("Lyon", "Nice", "2026-02-15", "2-0", "Home")
    ]

    updated_count = 0
    
    print("Updates to apply:")
    for home, away, date, score, result in updates:
        print(f"  {home} vs {away} ({date}) -> {score} ({result})")

    for index, row in df_pred.iterrows():
        match_name = str(row.get("Match", ""))
        date_val = str(row.get("Date", ""))
        
        for home, away, date_part, score, result in updates:
            if home in match_name and away in match_name and date_part in date_val:
                print(f"Updating row {index}: {match_name} ({date_val})")
                df_pred.at[index, "Actual_Score"] = score
                df_pred.at[index, "Actual_Result"] = result
                updated_count += 1

    if updated_count > 0:
        sheets["Predictions"] = df_pred
        with pd.ExcelWriter(file_path, engine="openpyxl", mode="w") as writer:
            for sheet_name, df in sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        print(f"Successfully updated {updated_count} matches in 'Predictions' sheet.")
    else:
        print("No matches found to update.")

except Exception as e:
    print(f"An error occurred: {e}")
