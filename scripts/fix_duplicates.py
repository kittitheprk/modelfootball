import pandas as pd
import os

filename = "prediction_tracker.xlsx"

if os.path.exists(filename):
    print(f"Fixing duplicates in {filename}...")
    try:
        xl = pd.ExcelFile(filename)
        updated = False
        dfs = {}

        # Fix Predictions Sheet
        if 'Predictions' in xl.sheet_names:
            df = pd.read_excel(filename, sheet_name='Predictions')
            initial_len = len(df)
            
            # Identify entries for 'Rayo Vallecano vs ...'
            # We want to keep the one that matches 'Bet Data' or just the latest one.
            # Row 18: ... vs Atletico Madrid
            # Row 19: ... vs Atltico Madrid
            
            # Let's simple remove the one representing the "older" or "less correct" version.
            # Since 'bet data' has the 'Atltico' one (likely from Python script), 
            # we should probably keep that one for consistency, OR rename both to 'Atletico' (safe ASCII).
            
            # Decision: Normalize to 'Atletico' (Safe)
            df['Match'] = df['Match'].str.replace('Atlético', 'Atletico').str.replace('Atltico', 'Atletico')
            
            # Now deduplicate
            df = df.drop_duplicates(subset=['Match', 'Date'], keep='last')
            
            if len(df) < initial_len or initial_len > 0: # Checks if we changed anything
                 dfs['Predictions'] = df
                 updated = True
                 print(f"Predictions: Normalized names and removed {initial_len - len(df)} duplicates.")

        # Fix Bet Data Sheet
        if 'bet data' in xl.sheet_names:
            df_bet = pd.read_excel(filename, sheet_name='bet data')
            initial_len_bet = len(df_bet)
            
            # Normalize here too
            df_bet['Match'] = df_bet['Match'].str.replace('Atlético', 'Atletico').str.replace('Atltico', 'Atletico')
            
            df_bet = df_bet.drop_duplicates(subset=['Match', 'Date'], keep='last')
            
            dfs['bet data'] = df_bet
            updated = True # Always save to be safe with normalization

        if updated:
            with pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                if 'Predictions' in dfs:
                    dfs['Predictions'].to_excel(writer, sheet_name='Predictions', index=False)
                if 'bet data' in dfs:
                    dfs['bet data'].to_excel(writer, sheet_name='bet data', index=False)
            print("Fix complete. Names normalized to 'Atletico'.")

    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"{filename} not found.")
