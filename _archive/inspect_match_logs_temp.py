import os
import glob
import pandas as pd
import datetime

BASE_DIR = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football"
MATCH_LOGS_DIR = os.path.join(BASE_DIR, "Match Logs")

def inspect_match_logs():
    print(f"Inspecting Match Logs in: {MATCH_LOGS_DIR}")
    
    # 1. Check file timestamps
    files = []
    for root, dirs, filenames in os.walk(MATCH_LOGS_DIR):
        for f in filenames:
            if f.endswith(".xlsx") or f.endswith(".csv"):
                files.append(os.path.join(root, f))
    
    if not files:
        print("No match log files found.")
        return

    latest_file = max(files, key=os.path.getmtime)
    timestamp = os.path.getmtime(latest_file)
    dt_object = datetime.datetime.fromtimestamp(timestamp)
    print(f"Latest file modification time: {dt_object} ({os.path.basename(latest_file)})")

    # 2. Check content for latest date
    # Assuming standard format, look for a 'Date' column
    try:
        df = pd.read_excel(latest_file) if latest_file.endswith('.xlsx') else pd.read_csv(latest_file)
        
        date_col = None
        for col in df.columns:
            if 'date' in col.lower():
                date_col = col
                break
        
        if date_col:
            print(f"Found date column: {date_col}")
            # Try to convert to datetime to find max
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            max_date = df[date_col].max()
            print(f"Latest match date in file: {max_date}")
        else:
            print("No 'Date' column found in the file.")
            print("Columns:", df.columns.tolist())
            
            # Peek at first few rows
            print("\nFirst 3 rows:")
            print(df.head(3).to_string())

    except Exception as e:
        print(f"Error reading file content: {e}")

if __name__ == "__main__":
    inspect_match_logs()
