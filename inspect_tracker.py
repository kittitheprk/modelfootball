
import pandas as pd
import os

def inspect_tracker():
    filename = "prediction_tracker.xlsx"
    if not os.path.exists(filename):
        print("Tracker not found.")
        return

    try:
        xl = pd.ExcelFile(filename)
        print("Sheets:", xl.sheet_names)
        
        target_match = "AS Monaco vs Paris Saint-Germain"
        
        if "bet predic" in xl.sheet_names:
            df = pd.read_excel(filename, sheet_name="bet predic")
            print(f"\n--- Sheet: bet predic (Rows for {target_match}) ---")
            # Filter loosely
            matches = df[df["Match"].astype(str).str.contains("Monaco", case=False, na=False)]
            if not matches.empty:
                print(matches[["Date", "Match", "Selected_Bet", "Model_Prob", "Confidence"]].to_string())
            else:
                print("No matches found in 'bet predic'.")

        if "Predictions" in xl.sheet_names:
            df = pd.read_excel(filename, sheet_name="Predictions")
            print(f"\n--- Sheet: Predictions (Rows for {target_match}) ---")
            matches = df[df["Match"].astype(str).str.contains("Monaco", case=False, na=False)]
            if not matches.empty:
                cols = [c for c in ["Date", "Match", "Pred_Score", "Pred_Result"] if c in df.columns]
                print(matches[cols].to_string())
            else:
                print("No matches found in 'Predictions'.")

    except Exception as e:
        print(f"Error reading excel: {e}")

if __name__ == "__main__":
    inspect_tracker()
