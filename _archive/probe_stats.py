import requests
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "Accept-Language": "en-US,en;q=0.9"
}

# Erling Haaland / Premier League 24/25
# Check ID: https://www.sofascore.com/football/player/erling-haaland/839956
PLAYER_ID = 839956
TOURNAMENT_ID = 17 # Premier League
SEASON_ID = 61627 # Need to check if this is current. 
# In scrape_player_positions, PL is 76986. Let's use that.
SEASON_ID = 76986 

def probe():
    url = f"https://api.sofascore.com/api/v1/player/{PLAYER_ID}/unique-tournament/{TOURNAMENT_ID}/season/{SEASON_ID}/statistics/overall"
    print(f"Fetching: {url}")
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("\nSUCCESS. Keys found:")
            print(data.keys())
            
            print("\nSample Data (first 500 chars):")
            print(str(data)[:500])
            
            # Save to file for full inspection if needed (or just print important sections)
            with open("stats_probe.json", "w") as f:
                json.dump(data, f, indent=2)
            print("\nSaved full JSON to stats_probe.json")
            
        else:
            print(f"Error: {response.status_code}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    probe()
