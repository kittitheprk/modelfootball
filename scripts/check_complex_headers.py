
import pandas as pd
import os

file_path = r"d:\model footbal\output_opta\Bundesliga\Hoffenheim.xlsx"

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    exit()

print(f"Checking Complex Columns in: {file_path}\n")

# 1. Check PASSING (Open Play, Final Third, Crosses)
try:
    df = pd.read_excel(file_path, sheet_name="Passing")
    cols = list(df.columns)
    print("--- Sheet: Passing ---")
    
    # Filter for interesting columns
    interesting = [c for c in cols if "Passes" in c or "Final Third" in c or "Crosses" in c]
    for c in interesting:
        print(f"  Found: {c}")
        
except Exception as e:
    print(f"Error reading Passing: {e}")

print("\n")

# 2. Check DEFENDING (Duels)
try:
    df = pd.read_excel(file_path, sheet_name="Defending")
    cols = list(df.columns)
    print("--- Sheet: Defending ---")
    
    interesting = [c for c in cols if "Duels" in c]
    for c in interesting:
        print(f"  Found: {c}")

except Exception as e:
    print(f"Error reading Defending: {e}")

print("\n")

# 3. Check CARRYING (Carries, Progressive, Ended With)
try:
    df = pd.read_excel(file_path, sheet_name="Carrying")
    cols = list(df.columns)
    print("--- Sheet: Carrying ---")
    
    # Filter
    interesting = [c for c in cols if "Carries" in c or "Progressive" in c or "Ended" in c]
    for c in interesting:
        print(f"  Found: {c}")

except Exception as e:
    print(f"Error reading Carrying: {e}")
