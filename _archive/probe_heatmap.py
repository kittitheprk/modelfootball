import requests
import json
import time
import random

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "Accept-Language": "en-US,en;q=0.9"
}

# Raphinha / La Liga 24/25
PLAYER_ID = 831005
TOURNAMENT_ID = 8 # La Liga
SEASON_ID = 61643 # This might be old, let's double check the season ID from previous scripts, users script had 77559

# Let's try both season IDs just to be safe
SEASON_IDS = [77559, 61643, 52380] 

def get_json(url):
    try:
        print(f"Fetching: {url}")
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  Error: {response.status_code}")
    except Exception as e:
        print(f"  Exception: {e}")
    return None

def probe():
    # 1. Verify Season ID first (using standings or something reliable)
    # Actually let's just try the one we used in scrape_player_positions.py which seemed recent: 77559
    # And maybe list seasons for the player to be sure?
    
    print("--- Probing Heatmap Endpoints ---")
    
    target_s_id = 77559
    
    # Potential Endpoints
    endpoints = [
        # Common pattern
        f"https://api.sofascore.com/api/v1/player/{PLAYER_ID}/unique-tournament/{TOURNAMENT_ID}/season/{target_s_id}/heatmap/overall",
        f"https://api.sofascore.com/api/v1/player/{PLAYER_ID}/heatmap/season/{target_s_id}",
        # Maybe embedded in statistics?
        f"https://api.sofascore.com/api/v1/player/{PLAYER_ID}/unique-tournament/{TOURNAMENT_ID}/season/{target_s_id}/statistics/overall"
    ]

    for url in endpoints:
        data = get_json(url)
        if data:
            print(f"\nSUCCESS: Data found at {url}")
            keys = list(data.keys())
            print(f"Keys: {keys}")
            
            # Check for coordinates
            if 'heatmap' in data:
                print("Found 'heatmap' key!")
                # Print sample
                print(str(data['heatmap'])[:200])
            elif isinstance(data, list) and len(data) > 0 and 'x' in data[0] and 'y' in data[0]:
                 print("Found list of coordinates directly!")
                 print(str(data)[:200])
            elif 'points' in data:
                 print("Found 'points' key!")
                 print(str(data['points'])[:200])
            else:
                 print("Structure unclear, saving to probe_result.json")
                 with open("probe_result.json", "w") as f:
                     json.dump(data, f, indent=2)
            
            return # Stop after first success

    print("\nNo direct heatmap endpoints worked.")

if __name__ == "__main__":
    probe()
