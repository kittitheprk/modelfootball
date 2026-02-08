import json
import os
import glob
import datetime

BASE_DIR = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football"
DASHBOARD_DATA = os.path.join(BASE_DIR, "dashboard", "data.json")
ALL_STATS_DIR = os.path.join(BASE_DIR, "all stats")
SOFASCORE_DIR = os.path.join(BASE_DIR, "sofascore_team_data")

def get_file_info(directory, pattern):
    files = glob.glob(os.path.join(directory, pattern))
    if not files:
        return "No files found", None
    
    # Get latest file time
    latest_file = max(files, key=os.path.getmtime)
    timestamp = os.path.getmtime(latest_file)
    dt_object = datetime.datetime.fromtimestamp(timestamp)
    return os.path.basename(latest_file), dt_object.strftime("%Y-%m-%d %H:%M:%S")

def main():
    # 1. Counts from dashboard data
    try:
        if os.path.exists(DASHBOARD_DATA):
            with open(DASHBOARD_DATA, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            teams = data.get("teams", [])
            players = data.get("players", [])
            print(f"DASHBOARD DATA COUNTS:")
            print(f"  Teams: {len(teams)}")
            print(f"  Players: {len(players)}")
        else:
            print(f"DASHBOARD DATA NOT FOUND: {DASHBOARD_DATA}")
    except Exception as e:
        print(f"Error reading dashboard data: {e}")

    # 2. File Timestamps (When we scraped it)
    print("\nLATEST SCRAPE TYMSTAMPS (Local File Time):")
    
    msg, time = get_file_info(ALL_STATS_DIR, "*.xlsx")
    print(f"  Stats (FBref): {time} ({msg})")
    
    msg, time = get_file_info(SOFASCORE_DIR, "*.xlsx")
    print(f"  SofaScore: {time} ({msg})")

    # 3. Check for specific update time inside json if available (metadata)
    try:
        if 'metadata' in data:
            print("\nMETADATA IN JSON:")
            print(json.dumps(data['metadata'], indent=2))
    except:
        pass

if __name__ == "__main__":
    main()
