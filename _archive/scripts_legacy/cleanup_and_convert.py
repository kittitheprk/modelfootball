import pandas as pd
import os

filename = "prediction_tracker.xlsx"

# Matches to clean up (delete duplicate rows)
targets = [
    "Rayo Vallecano vs Atlético Madrid",
    "Napoli vs Roma",
    "RB Leipzig vs Wolfsburg"
]

if os.path.exists(filename):
    print(f"Cleaning duplicates in {filename}...")
    try:
        updated = False
        xl = pd.ExcelFile(filename)
        sheets = xl.sheet_names
        
        dfs = {}
        for sheet in sheets:
            if sheet in ['Predictions', 'bet data']:
                df = pd.read_excel(filename, sheet_name=sheet)
                
                # Check for our targets
                # If we find multiple entries for these, keep only the FIRST one? 
                # Actually, the user wants new format. 
                # Since I can't easily recalculate the % for old rows without re-running analysis...
                # Wait, I can't re-run analysis for all at once easily without user prompting.
                # BUT, I just modified update_tracker to UPDATE if exists. 
                # So if I run "save" now, it will update the EXISTING row with new format?
                # The latest_prediction.json only holds the LAST match (RB Leipzig).
                
                # So for RB Leipzig, running save now should update it to %.
                # For Rayo and Napoli, they are already in the file with 0.xx format.
                # I should ideally remove them so the user re-runs? Or convert them in place?
                
                # Converting in place is safest and most helpful.
                if sheet == 'bet data':
                   for col in df.columns:
                       if 'HDP' in col or 'Over' in col or 'Under' in col:
                           # Check if value is likely probability ( < 1.0 )
                           # Multiply by 100
                            df[col] = df[col].apply(lambda x: x * 100 if isinstance(x, (int, float)) and x <= 1.0 else x)
                            # Round?
                            df[col] = df[col].apply(lambda x: round(x, 1) if isinstance(x, (int, float)) else x)
                   print("Converted probabilities to % in 'bet data'.")
                   updated = True
                
                # Remove true duplicates (same match, same date) if any
                initial_len = len(df)
                df = df.drop_duplicates(subset=['Match', 'Date'], keep='last')
                if len(df) < initial_len:
                    print(f"Removed {initial_len - len(df)} duplicate rows in '{sheet}'.")
                    updated = True
                
                dfs[sheet] = df
            
        if updated:
            with pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                for sheet in ['Predictions', 'bet data']:
                    if sheet in dfs:
                        dfs[sheet].to_excel(writer, sheet_name=sheet, index=False)
            print("Cleanup complete.")
        else:
            print("No changes needed.")

    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"{filename} not found.")
