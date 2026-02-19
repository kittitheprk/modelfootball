import pandas as pd
from pathlib import Path
import os

RAW_DIR = "sofascore_team_data"

def clean_raw_files():
    if not os.path.exists(RAW_DIR):
        print(f"Directory {RAW_DIR} not found.")
        return

    files = list(Path(RAW_DIR).glob("*_Team_Stats.xlsx"))
    print(f"Cleaning {len(files)} files in {RAW_DIR}...")

    for file_path in files:
        try:
            df = pd.read_excel(file_path)
            original_cols = list(df.columns)
            
            # Filter out columns ending with _per_90 or _per_game
            # But keep 'goalsPerGame' if it comes from API (SofaScore sometimes has it)
            # The user specifically mentioned *_per_90 from previous script.
            
            new_cols = [c for c in original_cols if not c.endswith("_per_90")]
            
            if len(new_cols) < len(original_cols):
                df = df[new_cols]
                df.to_excel(file_path, index=False)
                print(f"  [Cleaned] {file_path.name} (Removed {len(original_cols) - len(new_cols)} columns)")
            else:
                print(f"  [Skip] {file_path.name} (No derived columns found)")
                
        except Exception as e:
            print(f"  [Error] {file_path.name}: {e}")

if __name__ == "__main__":
    clean_raw_files()
