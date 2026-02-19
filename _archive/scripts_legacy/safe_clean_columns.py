import pandas as pd
import os

filename = 'prediction_tracker.xlsx'
columns_to_remove = [
    'H -1.5 (%)',
    'H -0.5 (%)',
    'H +0.5 (%)',
    'H +1.5 (%)',
    'Over 1.5 (%)',
    'Over 2.5 (%)',
    'Over 3.5 (%)',
    'BTTS (%)'
]

if os.path.exists(filename):
    try:
        # Step 1: Read 'Predictions' sheet
        # (Assuming it's the main sheet of interest. If others were lost, we can't do much.)
        # If openpyxl fails, then file is truly corrupted.
        df_predictions = pd.read_excel(filename, sheet_name='Predictions', engine='openpyxl')
        
        # Step 2: Remove Columns
        initial_cols = len(df_predictions.columns)
        cols_to_drop = [c for c in columns_to_remove if c in df_predictions.columns]
        
        if cols_to_drop:
            df_predictions = df_predictions.drop(columns=cols_to_drop)
            print(f"Removed {len(cols_to_drop)} columns.")
        else:
            print("No columns to remove found.")
            
        # Step 3: Check if there's a Summary sheet
        try:
            df_summary = pd.read_excel(filename, sheet_name='Summary', engine='openpyxl')
        except:
            # Summary sheet might not exist or failed to load
            df_summary = None
            
        # Step 4: Write back
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df_predictions.to_excel(writer, sheet_name='Predictions', index=False)
            if df_summary is not None:
                df_summary.to_excel(writer, sheet_name='Summary', index=False)
        
        print(f"Successfully cleaned columns from {filename}")

    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"{filename} not found.")
