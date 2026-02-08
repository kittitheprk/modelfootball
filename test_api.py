
import requests
import json
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "Accept-Language": "en-US,en;q=0.9"
}

def get_json(url):
    try:
        print(f"Fetching: {url}")
        time.sleep(1)
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

# Test 1: Get PSG Players (Team ID 1644)
team_id = 1644
players_url = f"https://api.sofascore.com/api/v1/team/{team_id}/players"
players_data = get_json(players_url)

if players_data:
    print(f"\nFound {len(players_data.get('players', []))} players for Team {team_id}")
    # Print first player to see structure
    if len(players_data.get('players', [])) > 0:
        first_player = players_data['players'][0]
        print("Sample Player Data:", json.dumps(first_player.get('player'), indent=2))
else:
    print("Failed to get players.")

# Test 2: Get Dembele Details (Player ID 818244)
player_id = 818244
player_url = f"https://api.sofascore.com/api/v1/player/{player_id}"
player_data = get_json(player_url)

if player_data:
    print("\nPlayer Profile Data:", json.dumps(player_data, indent=2))
    
# Test 3: Get Characteristics (Strengths/Weaknesses/Positions?)
chars_url = f"https://api.sofascore.com/api/v1/player/{player_id}/characteristics"
chars_data = get_json(chars_url)
if chars_data:
    print("\nPlayer Characteristics Data:", json.dumps(chars_data, indent=2))
else:
    print("No characteristics data found via API.")
