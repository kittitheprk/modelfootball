import json
import os

BASE_DIR = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football"
DATA_FILE = os.path.join(BASE_DIR, "dashboard", "data.json")

def count_players():
    if not os.path.exists(DATA_FILE):
        print(f"Error: {DATA_FILE} does not exist.")
        return

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        players = data.get("players", [])
        print(f"Total players in dashboard/data.json: {len(players)}")
        
        # Optional: Print count by league
        leagues = {}
        for p in players:
            l = p.get('league', 'Unknown')
            leagues[l] = leagues.get(l, 0) + 1
            
        print("\nPlayers by League:")
        for l, count in leagues.items():
            print(f"  {l}: {count}")
            
    except Exception as e:
        print(f"Error reading data.json: {e}")

if __name__ == "__main__":
    count_players()
