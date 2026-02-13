import pandas as pd
import os

file_path = "all stats/Premier_League_Stats.xlsx"
print(f"Checking file: {file_path}")

try:
    xl = pd.ExcelFile(file_path)
    print("Sheet names:", xl.sheet_names)
    
    # Check 'Shooting' sheet
    if 'Shooting' in xl.sheet_names:
        df = pd.read_excel(file_path, sheet_name='Shooting')
        print("\n--- Shooting Sheet Head ---")
        print(df.head())
        print("\n--- Columns ---")
        print(df.columns.tolist())
    else:
        print("Shooting sheet not found!")

except Exception as e:
    print(f"Error: {e}")
