import requests
import pandas as pd
import time
import os
import random

# Global Counter
request_count = 0

# Configuration
OUTPUT_BASE_DIR = "heatmap"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "Accept-Language": "en-US,en;q=0.9"
}

LEAGUE_CONFIG = {
    "Premier_League": {"t_id": 17, "s_id": 76986},
    "La_Liga": {"t_id": 8, "s_id": 77559},
    "Bundesliga": {"t_id": 35, "s_id": 77333},
    "Serie_A": {"t_id": 23, "s_id": 76457},
    "Ligue_1": {"t_id": 34, "s_id": 77356}
}

def get_json(url, retries=3):
    global request_count
    request_count += 1
    
    # Long break every 50 requests
    if request_count % 50 == 0:
        print("     Taking a short break (15s)...")
        time.sleep(15)

    for i in range(retries):
        try:
            # Increased delay to avoid rate limiting (3-6 seconds)
            sleep_time = random.uniform(3.0, 6.0)
            time.sleep(sleep_time)
            
            print(f"    Fetching: {url}")
            response = requests.get(url, headers=HEADERS, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None
            elif response.status_code == 403:
                print(f"    CRITICAL: 403 Forbidden. The server is blocking requests.")
                print(f"    Stopping execution to prevent longer ban.")
                # Raise an exception to stop the entire script
                raise Exception("Blocked by Server (403)")
            else:
                print(f"    Error {response.status_code}")
                time.sleep(5) # Wait a bit before retry on 5xx errors
        except Exception as e:
            if "Blocked by Server" in str(e):
                raise e # Propagate the stop signal
            print(f"    Exception {e}")
            time.sleep(5)
    return None

def scrape_league_heatmaps(league_name, t_id, s_id):
    league_dir = os.path.join(OUTPUT_BASE_DIR, league_name)
    if not os.path.exists(league_dir):
        os.makedirs(league_dir)

    print(f"\n--- Processing {league_name} ---")

    # 1. Get Teams from Standings
    standings_url = f"https://api.sofascore.com/api/v1/unique-tournament/{t_id}/season/{s_id}/standings/total"
    standings_data = get_json(standings_url)
    
    if not standings_data:
        print(f"Failed to get standings for {league_name}")
        return

    teams = []
    try:
        for row in standings_data['standings'][0]['rows']:
            teams.append({
                'name': row['team']['name'],
                'id': row['team']['id']
            })
    except Exception as e:
        print(f"Error parsing standings: {e}")
        return

    print(f"Found {len(teams)} teams.")

    # 2. Process each Team
    for team in teams:
        team_name = team['name']
        team_id = team['id']
        file_path = os.path.join(league_dir, f"{team_name}_heatmaps.xlsx")



        print(f"  Scraping Heatmaps for {team_name} (ID: {team_id})...")
        
        # Get Players
        players_url = f"https://api.sofascore.com/api/v1/team/{team_id}/players"
        players_resp = get_json(players_url)
        
        if not players_resp or 'players' not in players_resp:
            print(f"    No players found for {team_name}")
            continue

        heatmap_data_list = []
        
        for p_entry in players_resp['players']:
            player = p_entry['player']
            p_id = player['id']
            p_name = player.get('name', 'Unknown')
            
            # Fetch Heatmap
            heatmap_url = f"https://api.sofascore.com/api/v1/player/{p_id}/unique-tournament/{t_id}/season/{s_id}/heatmap/overall"
            heatmap_resp = get_json(heatmap_url)
            
            if heatmap_resp and 'points' in heatmap_resp:
                points = heatmap_resp['points']
                # Flatten points
                for pt in points:
                    heatmap_data_list.append({
                        'League': league_name,
                        'Team': team_name,
                        'Player_Name': p_name,
                        'Player_ID': p_id,
                        'X': pt.get('x'),
                        'Y': pt.get('y'),
                        'Count': pt.get('count')
                    })
            else:
                 # It's common for some players (e.g. bench) to have no heatmap data
                 pass
        
        # Save Team Data
        if heatmap_data_list:
            df = pd.DataFrame(heatmap_data_list)
            df.to_excel(file_path, index=False)
            print(f"    Saved {len(heatmap_data_list)} data points to {file_path}")
        else:
            print(f"    No heatmap data found for {team_name}")

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_BASE_DIR):
        os.makedirs(OUTPUT_BASE_DIR)
        
    for league, config in LEAGUE_CONFIG.items():
        scrape_league_heatmaps(league, config['t_id'], config['s_id'])
