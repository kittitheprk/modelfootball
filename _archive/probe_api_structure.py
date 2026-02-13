import requests
import json
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "Accept-Language": "en-US,en;q=0.9"
}

def probe():
    try:
        # Man City ID 17
        print("Fetching players...")
        resp = requests.get("https://api.sofascore.com/api/v1/team/17/players", headers=HEADERS)
        if resp.status_code != 200:
            print(f"Failed to get players: {resp.status_code}")
            return

        players = resp.json().get('players', [])
        if not players:
            print("No players found")
            return

        # Pick a player, preferably one with likely multiple positions if possible, but any will do for structure check
        p_id = players[0]['player']['id']
        p_name = players[0]['player'].get('name', 'Unknown')
        print(f"Probing player: {p_name} ({p_id})")

        time.sleep(1)
        chars_url = f"https://api.sofascore.com/api/v1/player/{p_id}/characteristics"
        c_resp = requests.get(chars_url, headers=HEADERS)
        if c_resp.status_code != 200:
             print(f"Failed to get chars: {c_resp.status_code}")
             return

        data = c_resp.json()
        positions = data.get('positions', [])
        print(f"Positions Type: {type(positions)}")
        print(f"Positions Content: {positions}")
        if positions:
            print(f"First Item Type: {type(positions[0])}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    probe()
