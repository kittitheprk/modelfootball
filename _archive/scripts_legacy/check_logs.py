import os
import pandas as pd
from glob import glob

base_dir = "Match Logs"
required_sheets = ["Shooting", "Goalkeeping"]
broken_files = []

print(f"Checking files in {base_dir}...")

for filepath in glob(os.path.join(base_dir, "**", "*.xlsx"), recursive=True):
    if os.path.basename(filepath).startswith("~$"): continue # Skip temp files
    
    try:
        xl = pd.ExcelFile(filepath)
        sheet_names = xl.sheet_names
        missing = [s for s in required_sheets if s not in sheet_names]
        
        if missing:
            print(f"[MISSING SHEETS] {filepath}: {missing}")
            broken_files.append(filepath)
        elif os.path.getsize(filepath) < 5000:
             print(f"[SMALL FILE] {filepath}: {os.path.getsize(filepath)} bytes")
             broken_files.append(filepath)
             
    except Exception as e:
        print(f"[CORRUPT] {filepath}: {e}")
        broken_files.append(filepath)

if broken_files:
    print(f"\nFound {len(broken_files)} problematic files.")
else:
    print("\nAll files look good!")
