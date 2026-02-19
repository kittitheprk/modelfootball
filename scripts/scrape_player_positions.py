import requests
import pandas as pd
import time
import os
import random
import json

# Configuration
OUTPUT_BASE_DIR = "position"

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

# Mapping for Characteristic Types (found from common observation or we can just store the ID if mapping is unknown)
# For now, we will store the raw types or try to fetch a mapping if possible. 
# Actually, the user cares most about POSITIONS which are strings in the JSON.
# We will just save the "positions" list.

def get_json(url, retries=3):
    for i in range(retries):
        try:
            time.sleep(random.uniform(2.0, 4.0)) # Increased polite delay to avoid blocking
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                print(f"  404 Not Found: {url}")
                return None
            elif response.status_code == 403:
                print(f"  403 Forbidden: {url} (Sleeping longer)")
                time.sleep(10) # Increased penalty sleep
            else:
                print(f"  Error {response.status_code}: {url}")
        except Exception as e:
            print(f"  Exception {e}: {url}")
            time.sleep(5)
    return None

def scrape_league(league_name, t_id, s_id):
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
        file_path = os.path.join(league_dir, f"{team_name}_positions.xlsx")

        if os.path.exists(file_path):
            print(f"  Skipping {team_name}, file exists.")
            continue

        print(f"  Scraping {team_name} (ID: {team_id})...")
        
        # Get Players
        players_url = f"https://api.sofascore.com/api/v1/team/{team_id}/players"
        players_resp = get_json(players_url)
        
        if not players_resp or 'players' not in players_resp:
            print(f"    No players found for {team_name}")
            continue

        player_list = []
        
        for p_entry in players_resp['players']:
            player = p_entry['player']
            p_id = player['id']
            p_name = player.get('name', 'Unknown')
            p_slug = player.get('slug', '')
            
            # Basic info
            p_data = {
                'Name': p_name,
                'ID': p_id,
                'Slug': p_slug,
                'Team': team_name,
                'League': league_name,
                'Position_General': player.get('position', ''),
                'Jersey_Number': player.get('jerseyNumber', ''),
                'Height': player.get('height', ''),
                'Preferred_Foot': player.get('preferredFoot', ''),
                'Country': player.get('country', {}).get('name', ''),
            }

            # detailed characteristics (Positions specific)
            chars_url = f"https://api.sofascore.com/api/v1/player/{p_id}/characteristics"
            chars_data = get_json(chars_url)
            
            detailed_positions = []
            primary_pos = ""
            secondary_pos = ""
            strengths = [] # raw types
            weaknesses = [] # raw types

            if chars_data:
                detailed_positions = chars_data.get('positions', [])
                if detailed_positions:
                    # Sometimes it might be a list of strings directly, check first item
                    if isinstance(detailed_positions[0], dict):
                        # If it's a dict (unlikely for "positions" based on previous assumption but safe to check)
                        # Actually user said previously it was just strings. Let's assume strings.
                        pass
                    
                    primary_pos = detailed_positions[0]
                    if len(detailed_positions) > 1:
                        secondary_pos = ", ".join(detailed_positions[1:])
                
                # Store raw types for now as we don't have the map, but positions are strings
                strengths = [str(x.get('type')) for x in chars_data.get('positive', [])]
                weaknesses = [str(x.get('type')) for x in chars_data.get('negative', [])]

            p_data['Primary_Position'] = primary_pos
            p_data['Secondary_Positions'] = secondary_pos
            p_data['Detailed_Positions_All'] = ", ".join(detailed_positions) # Keeping mostly for debug/completeness
            p_data['Strengths_Codes'] = ", ".join(strengths)
            p_data['Weaknesses_Codes'] = ", ".join(weaknesses)
            
            player_list.append(p_data)
        
        # Save Team Data
        if player_list:
            df = pd.DataFrame(player_list)
            df.to_excel(file_path, index=False)
            print(f"    Saved {len(player_list)} players to {file_path}")
        else:
            print(f"    No player data to save for {team_name}")

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_BASE_DIR):
        os.makedirs(OUTPUT_BASE_DIR)
        
    for league, config in LEAGUE_CONFIG.items():
        scrape_league(league, config['t_id'], config['s_id'])
