import os
import pandas as pd
import glob

OUTPUT_DIR = r"d:\model footbal\output_opta"

REQUIRED_SHEETS = [
    "Attacking",
    "Passing",
    "Defending",
    "Carrying",
    "Goalkeeping"
]

# Key columns to check for in each sheet (loose check)
REQUIRED_COLUMNS = {
    "Attacking": ["goals", "xg", "shots"],
    "Passing": ["total", "successful"],
    "Defending": ["tackles", "interceptions"],
    "Carrying": ["carries", "progressive"],
    "Goalkeeping": ["saves made", "goals conceded"]
}

def validate_files():
    print(f"Scanning {OUTPUT_DIR}...\n")
    
    # Find all xlsx files recursively
    files = glob.glob(os.path.join(OUTPUT_DIR, "**", "*.xlsx"), recursive=True)
    
    print(f"Found {len(files)} files.")
    
    issues = []
    
    for i, file_path in enumerate(files):
        filename = os.path.basename(file_path)
        league = os.path.basename(os.path.dirname(file_path))
        
        try:
            xl = pd.ExcelFile(file_path)
            sheet_names = xl.sheet_names
            
            missing_sheets = [s for s in REQUIRED_SHEETS if s not in sheet_names]
            
            if missing_sheets:
                issues.append(f"[{league}/{filename}] Missing Sheets: {missing_sheets}")
                continue
            
            # Check content of each sheet
            for sheet in REQUIRED_SHEETS:
                df = pd.read_excel(file_path, sheet_name=sheet)
                
                if df.empty:
                     issues.append(f"[{league}/{filename}] Sheet '{sheet}' is EMPTY")
                     continue
                     
                # Check columns
                cols = [str(c).lower() for c in df.columns]
                
                # Check for Super Table abuse
                if len(cols) > 30:
                    issues.append(f"[{league}/{filename}] Sheet '{sheet}' has SUPER TABLE ({len(cols)} cols)")
                    continue

                req_cols = REQUIRED_COLUMNS.get(sheet, [])
                
                missing_cols = []
                for rc in req_cols:
                    # Handle synonyms
                    if rc == "interceptions":
                        if not any(x in str(cols) for x in ["interceptions", "ints"]):
                             missing_cols.append(rc)
                    elif rc == "goals conceded":
                         if not any(x in str(cols) for x in ["goals conceded", "goalsconceded", "gc"]):
                             missing_cols.append(rc)
                    else:
                        if not any(rc in c for c in cols):
                             missing_cols.append(rc)
                
                if missing_cols:
                    issues.append(f"[{league}/{filename}] Sheet '{sheet}' Missing Cols: {missing_cols}")

        except Exception as e:
            issues.append(f"[{league}/{filename}] Error reading file: {e}")

        # Progress
        if (i+1) % 10 == 0:
            print(f"Checked {i+1}/{len(files)} files...")

    print("\n" + "="*50)
    print("VALIDATION SUMMARY")
    print("="*50)
    
    if not issues:
        print("[OK] ALL FILES VALID! (All sheets present, basic columns check passed)")
    else:
        print(f"[FAIL] Found {len(issues)} issues:")
        for issue in issues:
            print(issue)
            
    # Export bad files list for repair
    bad_files = []
    
    # We need to re-iterate or change the loop to collect `bad_files`
    # Let's just modify the main loop to collect file_path when an issue is found.
    pass

def validate_and_collect():
    print(f"Scanning {OUTPUT_DIR}...\n")
    files = glob.glob(os.path.join(OUTPUT_DIR, "**", "*.xlsx"), recursive=True)
    print(f"Found {len(files)} files.")
    
    issues = []
    bad_files = set() 
    
    for i, file_path in enumerate(files):
        filename = os.path.basename(file_path)
        league = os.path.basename(os.path.dirname(file_path))
        is_bad = False
        
        # Check size first
        if os.path.getsize(file_path) < 100:
            issues.append(f"[{league}/{filename}] File size too small ({os.path.getsize(file_path)} bytes)")
            is_bad = True
            bad_files.add(file_path)
            continue
        
        try:
            with pd.ExcelFile(file_path, engine='openpyxl') as xl:
                sheet_names = xl.sheet_names
            
            # Check 1: Missing Sheets
            missing_sheets = [s for s in REQUIRED_SHEETS if s not in sheet_names]
            if missing_sheets:
                issues.append(f"[{league}/{filename}] Missing Sheets: {missing_sheets}")
                is_bad = True
            
            # Check 2: Sheet Content
            if not is_bad: # Only check deeper if basic check passed (or check all?)
                # let's check all to be thorough
                for sheet in REQUIRED_SHEETS:
                    if sheet not in sheet_names: continue
                    
                    df = pd.read_excel(file_path, sheet_name=sheet)
                    
                    if df.empty:
                         issues.append(f"[{league}/{filename}] Sheet '{sheet}' is EMPTY")
                         is_bad = True
                         continue
                         
                    cols = [str(c).lower() for c in df.columns]
                    
                    # Check 2.5: Raw Tuple Headers (Bad Flattening)
                    if any("('unnamed:" in c for c in cols):
                         issues.append(f"[{league}/{filename}] Sheet '{sheet}' has Raw Tuple Headers")
                         is_bad = True
                         # No need to check other things if headers are broken
                         continue
                    
                    # Check 3: Super Table
                    if len(cols) > 30:
                        issues.append(f"[{league}/{filename}] Sheet '{sheet}' has SUPER TABLE ({len(cols)} cols)")
                        is_bad = True
                        continue

                    # Check 4: Missing Cols
                    req_cols = REQUIRED_COLUMNS.get(sheet, [])
                    missing_cols = []
                    for rc in req_cols:
                        if rc == "interceptions":
                            if not any(x in str(cols) for x in ["interceptions", "ints"]):
                                 missing_cols.append(rc)
                        elif rc == "goals conceded":
                             if not any(x in str(cols) for x in ["goals conceded", "goalsconceded", "gc"]):
                                 missing_cols.append(rc)
                        else:
                            if not any(rc in c for c in cols):
                                 missing_cols.append(rc)
                    
                    if missing_cols:
                        issues.append(f"[{league}/{filename}] Sheet '{sheet}' Missing Cols: {missing_cols}")
                        # Don't mark bad for minor col miss? 
                        # Actually 'Defending' missing 'interceptions' is bad if we want complete data.
                        is_bad = True

        except Exception as e:
            issues.append(f"[{league}/{filename}] Error reading file: {e}")
            is_bad = True
            
        if is_bad:
            bad_files.add(file_path)

        if (i+1) % 20 == 0:
            print(f"Checked {i+1}/{len(files)} files...")

    print("\n" + "="*50)
    print("VALIDATION SUMMARY")
    print("="*50)
    
    if not issues:
        print("[OK] ALL FILES VALID!")
    else:
        print(f"[FAIL] Found {len(issues)} issues in {len(bad_files)} files.")
        print("First 10 issues:")
        for issue in issues[:10]:
            print(issue)
        
    import json
    with open("repair_targets.json", "w") as f:
        json.dump(list(bad_files), f, indent=2)
    print(f"Saved {len(bad_files)} files to 'repair_targets.json'")

if __name__ == "__main__":
    validate_and_collect()
