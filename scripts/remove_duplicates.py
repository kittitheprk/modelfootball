import pandas as pd
import os

filename = 'prediction_tracker.xlsx'

if os.path.exists(filename):
    try:
        df = pd.read_excel(filename, sheet_name='Predictions')
        original_count = len(df)
        
        # Drop duplicates based on Match and Date, keeping the last occurrence
        df_cleaned = df.drop_duplicates(subset=['Match', 'Date'], keep='last')
        cleaned_count = len(df_cleaned)
        
        if original_count > cleaned_count:
            # Save back
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df_cleaned.to_excel(writer, sheet_name='Predictions', index=False)
                # If we had a summary sheet, we might want to preserve it or recalculate it.
                # For now, let's just save Predictions. Ideally we should read all sheets.
                # Let's try to preserve other sheets if possible, but simplest is to just save Predictions 
                # and let update_tracker.py regenerate summary later if needed.
                # Actually, update_tracker.py generates summary every time it runs.
                # So saving just predictions is fine, but let's see if we can calc summary too.
                
                # ... (Summary calculation logic similar to update_tracker.py) ...
                # Or just save predictions for now.
            print(f"Removed {original_count - cleaned_count} duplicate rows.")
            print(f"Original: {original_count}, New: {cleaned_count}")
        else:
            print("No duplicates found.")
            
    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"{filename} not found.")
