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
        # Load sheets differently to avoid the zip reader error
        # We will read each sheet individually
        
        # First, get sheet names
        xl = pd.ExcelFile(filename, engine='openpyxl')
        sheet_names = xl.sheet_names
        
        sheet_data = {}
        for sheet in sheet_names:
             sheet_data[sheet] = pd.read_excel(filename, sheet_name=sheet, engine='openpyxl')

        # Process and save
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            for sheet, df in sheet_data.items():
                
                # Only remove columns from 'Predictions' sheet
                if sheet == 'Predictions':
                    cols_to_drop = [c for c in columns_to_remove if c in df.columns]
                    if cols_to_drop:
                        df = df.drop(columns=cols_to_drop)
                        print(f"Sheet '{sheet}': Removed {len(cols_to_drop)} columns.")
                    else:
                        print(f"Sheet '{sheet}': No columns to remove found.")
                
                df.to_excel(writer, sheet_name=sheet, index=False)
                
        print(f"Successfully cleaned columns from {filename}")
            
    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"{filename} not found.")
