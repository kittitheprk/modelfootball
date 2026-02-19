import pandas as pd
import os

filename = "prediction_tracker.xlsx"

if os.path.exists(filename):
    print(f"--- Checking {filename} ---\n")
    try:
        # Check Summary Sheet
        print(">>> SHEET: Summary")
        df_sum = pd.read_excel(filename, sheet_name='Summary')
        print(df_sum.to_string())
        
    except Exception as e:
        print(f"Error reading file: {e}")
else:
    print(f"{filename} not found.")
