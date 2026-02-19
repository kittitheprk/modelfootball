import pandas as pd
import os

filename = "prediction_tracker.xlsx"

if os.path.exists(filename):
    print(f"Opening {filename}...")
    try:
        # Load both sheets
        xl = pd.ExcelFile(filename)
        sheets = xl.sheet_names
        
        with pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            for sheet in sheets:
                if sheet in ['Predictions', 'bet data']:
                    df = pd.read_excel(filename, sheet_name=sheet)
                    # Check if last row is Arsenal vs Liverpool
                    if not df.empty and df.iloc[-1]['Match'] == "Arsenal vs Liverpool":
                        print(f"Removing last row from sheet '{sheet}': {df.iloc[-1]['Match']}")
                        df = df.iloc[:-1] # Remove last row
                        df.to_excel(writer, sheet_name=sheet, index=False)
                    else:
                        print(f"Last row in '{sheet}' is not Arsenal vs Liverpool. Skipping removal.")
    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"{filename} not found.")
