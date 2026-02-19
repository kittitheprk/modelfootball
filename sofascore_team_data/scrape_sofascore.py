import requests
import pandas as pd
import time
import os
import random

# Directory to save data
# "สร้างโฟเดอร์ใหม่" -> Create new folder
OUTPUT_FOLDER = "sofascore_team_data"
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# Headers to mimic a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "Accept-Language": "en-US,en;q=0.9"
}

# League Configurations found from the user's provided URLs
# Structure: Name -> (Tournament ID, Season ID)
# 1. La Liga: https://www.sofascore.com/tournament/football/spain/laliga/8#id:77559
# 2. Serie A: https://www.sofascore.com/tournament/football/italy/serie-a/23#id:76457
# 3. Bundesliga: https://www.sofascore.com/tournament/football/germany/bundesliga/35#id:77333
# 4. Premier League: https://www.sofascore.com/tournament/football/england/premier-league/17#id:76986
# 5. Ligue 1: https://www.sofascore.com/tournament/football/france/ligue-1/34#id:77356

LEAGUE_CONFIG = {
    "La_Liga": {"t_id": 8, "s_id": 77559},
    "Serie_A": {"t_id": 23, "s_id": 76457},
    "Bundesliga": {"t_id": 35, "s_id": 77333},
    "Premier_League": {"t_id": 17, "s_id": 76986},
    "Ligue_1": {"t_id": 34, "s_id": 77356}
}

def get_json(url):
    try:
        # Random delay to avoid rate limiting
        time.sleep(random.uniform(1.5, 3.5))
        print(f"Fetching: {url}")
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 403:
            print(f"Error 403: Access Denied for {url}")
        else:
            print(f"Error {response.status_code} for {url}")
    except Exception as e:
        print(f"Exception fetching {url}: {e}")
    return None

def flatten_stats(stats_json):
    """Recursively flatten the stats dictionary."""
    out = {}
    for key, value in stats_json.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                out[f"{key}_{sub_key}"] = sub_value
        else:
            out[key] = value
    return out

def scrape_teams_stats():
    for league_name, ids in LEAGUE_CONFIG.items():
        t_id = ids['t_id']
        s_id = ids['s_id']
        
        print(f"\nProcessing League: {league_name} (Tournament: {t_id}, Season: {s_id})")
        
        # 1. Get Standings to find all Teams in the league
        # API: https://api.sofascore.com/api/v1/unique-tournament/{t_id}/season/{s_id}/standings/total
        standings_url = f"https://api.sofascore.com/api/v1/unique-tournament/{t_id}/season/{s_id}/standings/total"
        standings_data = get_json(standings_url)
        
        if not standings_data:
            print(f"Failed to get standings for {league_name}. Skipping.")
            continue
            
        # Parse teams from standings
        teams_list = []
        try:
            # Usually standings[0] is the main table
            for row in standings_data['standings'][0]['rows']:
                team_info = row['team']
                teams_list.append({
                    'name': team_info['name'],
                    'id': team_info['id'],
                    'matches': row.get('matches', 0) 
                })
        except (KeyError, IndexError) as e:
            print(f"Error parsing standings for {league_name}: {e}")
            continue
            
        print(f"Found {len(teams_list)} teams in {league_name}. Scraping stats...")
        
        league_stats_data = []
        
        # 2. Scrape Stats for each Team
        for team in teams_list:
            team_name = team['name']
            team_id = team['id']
            matches_played = team['matches']
            
            # API to get Team Statistics for the SPECIFIC SEASON (Equivalent to selecting dropdown)
            # URL: https://api.sofascore.com/api/v1/team/{team_id}/unique-tournament/{t_id}/season/{s_id}/statistics/overall
            stats_url = f"https://api.sofascore.com/api/v1/team/{team_id}/unique-tournament/{t_id}/season/{s_id}/statistics/overall"
            
            stats_data = get_json(stats_url)
            
            if stats_data and 'statistics' in stats_data:
                # Flatten the statistics data
                flat_stats = flatten_stats(stats_data['statistics'])
                
                # Add metadata
                flat_stats['Team_Name'] = team_name
                flat_stats['Team_ID'] = team_id
                flat_stats['League'] = league_name
                flat_stats['Matches_Played'] = matches_played

                league_stats_data.append(flat_stats)
                print(f"  + Scraped stats for {team_name} (Matches: {matches_played})")
            else:
                print(f"  - No stats found for {team_name} (URL: {stats_url})")
        
        # 3. Save to Excel
        if league_stats_data:
            df = pd.DataFrame(league_stats_data)
            
            # Reorder columns to put Name/ID/Matches first
            front_cols = ['Team_Name', 'Team_ID', 'League', 'Matches_Played']
            cols = front_cols + [c for c in df.columns if c not in front_cols]
            df = df[cols]
            
            output_filename = f"{league_name}_Team_Stats.xlsx"
            output_path = os.path.join(OUTPUT_FOLDER, output_filename)
            
            df.to_excel(output_path, index=False)
            print(f"Saved {league_name} data to {output_path}")
        else:
            print(f"No data collected for {league_name}")

if __name__ == "__main__":
    scrape_teams_stats()
