import requests
import pandas as pd
import time
import os
import random

# Configuration
OUTPUT_BASE_DIR = "sofaplayer"

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
            # Safer delay: 2 to 4 seconds
            time.sleep(random.uniform(2.0, 4.0)) 
            print(f"    Fetching: {url}")
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return None
            elif response.status_code == 403:
                print(f"    403 Forbidden. Sleeping 60s...")
                time.sleep(60)
            else:
                print(f"    Error {response.status_code}")
        except Exception as e:
            print(f"    Exception {e}")
            time.sleep(10)
    return None

request_count = 0

def scrape_league_player_stats(league_name, t_id, s_id):
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
        file_path = os.path.join(league_dir, f"{team_name}_stats.xlsx")



        print(f"  Scraping Player Stats for {team_name} (ID: {team_id})...")
        
        # Get Players
        players_url = f"https://api.sofascore.com/api/v1/team/{team_id}/players"
        players_resp = get_json(players_url)
        
        if not players_resp or 'players' not in players_resp:
            print(f"    No players found for {team_name}")
            continue

        player_data_list = []
        
        for p_entry in players_resp['players']:
            player = p_entry['player']
            p_id = player['id']
            p_name = player.get('name', 'Unknown')
            
            # Fetch Statistics
            # URL: api/v1/player/{id}/unique-tournament/{tid}/season/{sid}/statistics/overall
            stats_url = f"https://api.sofascore.com/api/v1/player/{p_id}/unique-tournament/{t_id}/season/{s_id}/statistics/overall"
            stats_resp = get_json(stats_url)
            
            if stats_resp and 'statistics' in stats_resp:
                stats = stats_resp['statistics']
                
                # Base metadata
                row = {
                    'League': league_name,
                    'Team': team_name,
                    'Player_Name': p_name,
                    'Player_ID': p_id,
                }
                
                # Merge stats fields
                # We simply flatten the whole dictionary
                row.update(stats)
                
                # Remove nested objects if any (like statisticsType)
                if 'statisticsType' in row:
                    del row['statisticsType']
                
                player_data_list.append(row)
            else:
                 pass # No stats for this player (maybe no appearances)
        
        # Save Team Data
        if player_data_list:
            df = pd.DataFrame(player_data_list)
            
            # Define desired order based on SofaScore UI Groups
            # Metadata first
            meta_cols = ['League', 'Team', 'Player_Name', 'Player_ID']
            
            # Matches
            matches_cols = ['rating', 'appearances', 'matchesStarted', 'minutesPlayed', 'totwAppearances']
            
            # Attacking
            attack_cols = [
                'goals', 'expectedGoals', 'scoringFrequency', 'goalsPerGame', # derived?
                'totalShots', 'shotsOnTarget', 'bigChancesMissed', 'goalConversionPercentage',
                'penaltyGoals', 'penaltyConversion', 'freeKickGoal', 
                'goalsFromInsideTheBox', 'goalsFromOutsideTheBox', 'headedGoals', 
                'leftFootGoals', 'rightFootGoals', 'hitWoodwork'
            ]
            
            # Passing
            passing_cols = [
                'assists', 'expectedAssists', 'touches', 'bigChancesCreated', 'keyPasses',
                'accuratePasses', 'accuratePassesPercentage', 'totalPasses',
                'accurateOwnHalfPasses', 'accurateOppositionHalfPasses', 'accurateFinalThirdPasses',
                'accurateLongBalls', 'accurateLongBallsPercentage', 
                'accurateCrosses', 'accurateCrossesPercentage'
            ]
            
            # Defending
            defend_cols = [
                'interceptions', 'tackles', 'possessionWonAttThird', 'ballRecovery', 
                'dribbledPast', 'clearances', 'blockedShots', 
                'errorLeadToShot', 'errorLeadToGoal', 'penaltyConceded'
            ]
            
            # Other / Duels
            other_cols = [
                'successfulDribbles', 'successfulDribblesPercentage', 
                'totalDuelsWon', 'totalDuelsWonPercentage',
                'groundDuelsWon', 'groundDuelsWonPercentage', 
                'aerialDuelsWon', 'aerialDuelsWonPercentage',
                'possessionLost', 'fouls', 'wasFouled', 'offsides',
                'yellowCards', 'redCards'
            ]

            # Goalkeeping (if exists)
            gk_cols = ['saves', 'cleanSheet', 'goalsConceded', 'penaltySave']

            # Combine all preferred columns
            desired_order = meta_cols + matches_cols + attack_cols + passing_cols + defend_cols + other_cols + gk_cols
            
            # Get existing columns in DF
            existing_cols = list(df.columns)
            
            # 1. Select columns that exist in both lists, respecting desired order
            final_cols = [c for c in desired_order if c in existing_cols]
            
            # 2. Append any remaining columns that were in the DF but not in our list
            remaining = [c for c in existing_cols if c not in final_cols]
            final_cols.extend(remaining)
            
            # Apply sorting
            df = df[final_cols]
            
            df.to_excel(file_path, index=False)
            print(f"    Saved {len(player_data_list)} players to {file_path}")
        else:
            print(f"    No statistics data found for {team_name}")

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_BASE_DIR):
        os.makedirs(OUTPUT_BASE_DIR)
        
    for league, config in LEAGUE_CONFIG.items():
        scrape_league_player_stats(league, config['t_id'], config['s_id'])
