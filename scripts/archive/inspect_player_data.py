import pandas as pd
import os

files = [
    "sofaplayer/Premier_League/Arsenal_stats.xlsx"
]

for f in files:
    if os.path.exists(f):
        print(f"\n--- Inspecting {f} ---")
        try:
            df = pd.read_excel(f)
            print("Columns:", df.columns.tolist())
            print(df.head(3).to_string())
        except Exception as e:
            print(f"Error: {e}")
    else:
        print(f"File not found: {f}")
