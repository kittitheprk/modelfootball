import pandas as pd
import os

filename = "prediction_tracker.xlsx"

if os.path.exists(filename):
    print(f"--- Checking {filename}: Summary Sheet ---\n")
    try:
        # Read the whole sheet (no header initially to see structure)
        df_sum = pd.read_excel(filename, sheet_name='Summary', header=None)
        
        # Print first 60 rows to see the blocks
        print(df_sum.head(60).to_string())
        
    except Exception as e:
        print(f"Error reading file: {e}")
else:
    print(f"{filename} not found.")
