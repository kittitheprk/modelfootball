
import pandas as pd
import requests
import json
import sys
import os
import simulator
import visualizer

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "AIzaSyBuBznv-XRM-Q7ThdTq_dlO8Z78UyN3r60"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"

def load_team_stats(league):
    # Map league names if necessary
    league_map = {
        'Bundesliga': 'Bundesliga', 'Premier League': 'Premier_League', 
        'La Liga': 'La_Liga', 'Serie A': 'Serie_A', 'Ligue 1': 'Ligue_1'
    }
    
    # Simple fuzzy search for file
    base_dir = "sofascore_team_data"
    for file in os.listdir(base_dir):
        if league in file:
            try:
                return pd.read_excel(os.path.join(base_dir, file))
            except:
                pass
    return None

def calculate_league_averages(team_df):
    if team_df is None:
        return {'avg_goals_home': 1.5, 'avg_goals_away': 1.2} # Fallback
    
    avg_goals_scored = team_df['goalsScored_per_90'].mean()
    avg_goals_conceded = team_df['goalsConceded_per_90'].mean()
    # Approx home/away split if not explicit
    return {'avg_goals_home': avg_goals_scored * 1.1, 'avg_goals_away': avg_goals_scored * 0.9}

def get_team_style_stats(team_df, team_name):
    if team_df is None: return None
    
    # Find team
    row = team_df[team_df['Team_Name'].str.contains(team_name, case=False, na=False)]
    if row.empty: return None
    row = row.iloc[0]
    
    # Calculate Style Metrics -> Handle Errors gracefully
    try:
        tackles = row.get('tackles', 0)
        interceptions = row.get('interceptions', 0)
        fouls = row.get('fouls', 0)
        passes_allowed = row.get('totalPassesAgainst', 1)
        
        ppda = passes_allowed / (tackles + interceptions + fouls) if (tackles+interceptions+fouls) > 0 else 0
        
        long_balls = row.get('totalLongBalls', 0)
        total_pass = row.get('totalPasses', 1)
        directness = (long_balls / total_pass) * 100
        
        poss = row.get('averageBallPossession', 50)
        
        return {
            'PPDA': round(ppda, 2),
            'Directness': round(directness, 2),
            'Possession': poss,
            'GoalsScored': row.get('goalsScored_per_90', 0),
            'GoalsConceded': row.get('goalsConceded_per_90', 0),
            'CleanSheets': row.get('cleanSheets', 0)
        }
    except Exception as e:
        print(f"Error calcing style for {team_name}: {e}")
        return None

def get_player_percentiles(df, player_name):
    # Columns for Pizza Chart
    cols = [
        'Non_Penalty_Goals_Per90_Pct', 'npxG_Per90_Pct', 'Shots_Total_Per90_Pct', 
        'Assists_Per90_Pct', 'Shot_Creating_Actions_Per90_Pct', 
        'Pass_Completion_Pct_Per90_Pct', 'Progressive_Passes_Per90_Pct', 'Progressive_Carries_Per90_Pct',
        'Tackles_Per90_Pct', 'Interceptions_Per90_Pct', 'Aerials_Won_Per90_Pct', 'Clearances_Per90_Pct'
    ]
    
    # Raw value cols (for verifying or display)
    # Just grab the percentiles
    player = df[df['Player'] == player_name]
    if player.empty: return None, None
    
    vals = []
    for c in cols:
        vals.append(player.iloc[0].get(c, 0))
        
    return vals, player.iloc[0]

def main():
    home_name = "Liverpool"
    away_name = "Manchester City"
    
    print(f"Loading data... analyzing {home_name} vs {away_name}")
    
    # 1. Load Player Data
    try:
        player_df = pd.read_excel('charts/final_chart_data.xlsx')
    except Exception as e:
        print(f"Error loading player data: {e}")
        player_df = pd.DataFrame() # Empty DF so we don't crash

    # 2. Identify League -> Force Premier League since player data is missing
    league = "Premier_League"
    print(f"Detected League: {league}")
    
    # 3. Load Team Data
    team_df = load_team_stats(league)
    
    if team_df is None:
        print(f"Could not load team data for {league}")
        return

    # 4. Calculate Team Styles
    home_style = get_team_style_stats(team_df, home_name)
    away_style = get_team_style_stats(team_df, away_name)
    
    if not home_style: print(f"Could not find stats for {home_name}")
    if not away_style: print(f"Could not find stats for {away_name}")

    # 5. Simulation (if team stats available)
    sim_result = "Simulation data unavailable."
    if home_style and away_style:
        league_stats = calculate_league_averages(team_df)
        sim_data = simulator.simulate_match(
            home_name, away_name, 
            {'goals_scored_per_game': home_style['GoalsScored'], 'goals_conceded_per_game': home_style['GoalsConceded']},
            {'goals_scored_per_game': away_style['GoalsScored'], 'goals_conceded_per_game': away_style['GoalsConceded']},
            league_stats
        )
        sim_result = f'''
        **ผลการจำลองการแข่งขัน 300 นัด (Match Simulation):**
        - {home_name} ชนะ: {sim_data['home_win_prob']:.1f}%
        - เสมอ: {sim_data['draw_prob']:.1f}%
        - {away_name} ชนะ: {sim_data['away_win_prob']:.1f}%
        - สกอร์ที่น่าจะเกิดขึ้นที่สุด: {sim_data['most_likely_score']}
        '''
        
        # Draw Comparison Chart based on Style metrics
        labels = ['Possession %', 'PPDA (Lower is Aggressive)', 'Directness %', 'Goals Scored/90', 'Goals Conceded/90']
        h_vals = [home_style['Possession'], home_style['PPDA'], home_style['Directness'], home_style['GoalsScored']*10, home_style['GoalsConceded']*10]
        a_vals = [away_style['Possession'], away_style['PPDA'], away_style['Directness'], away_style['GoalsScored']*10, away_style['GoalsConceded']*10]
        try:
            comp_chart = visualizer.create_comparison_chart(home_name, away_name, labels, h_vals, a_vals)
            print(f"Comparison Chart generated: {comp_chart}")
        except Exception as e:
            print(f"Error generating comparison chart: {e}")
    
    # 6. Generate Pizza Charts for Key Players (Top SCAs) - SKIPPED if player not found
    if not player_df.empty:
        home_players = player_df[player_df['Squad'].str.contains(home_name, case=False)]
        if not home_players.empty:
            key_home = home_players.sort_values(by='Shot_Creating_Actions', ascending=False).iloc[0]
            home_pizza_vals, _ = get_player_percentiles(player_df, key_home['Player'])
            if home_pizza_vals:
                p_chart = visualizer.create_pizza_chart(key_home['Player'], [], home_pizza_vals)
                print(f"Pizza Chart generated: {p_chart}")

        away_players = player_df[player_df['Squad'].str.contains(away_name, case=False)]
        if not away_players.empty:
            key_away = away_players.sort_values(by='Shot_Creating_Actions', ascending=False).iloc[0]
            away_pizza_vals, _ = get_player_percentiles(player_df, key_away['Player'])
            if away_pizza_vals:
                p_chart2 = visualizer.create_pizza_chart(key_away['Player'], [], away_pizza_vals)
                print(f"Pizza Chart generated: {p_chart2}")

    # 7. Construct AI Prompt
    prompt = f'''
คุณคือนักวิเคราะห์ฟุตบอล. จงวิเคราะห์คู่ **{home_name}** vs **{away_name}**.

**ข้อมูลสไตล์การเล่น (Team Style Profiling):**
(ถ้ามีข้อมูล: PPDA ยิ่งน้อยยิ่ง Pressing หนัก, Directness ยิ่งเยอะยิ่งเล่นบอลยาว)
- {home_name}: {home_style if home_style else 'N/A'}
- {away_name}: {away_style if away_style else 'N/A'}

{sim_result}

**คำแนะนำ:**
1. วิเคราะห์สไตล์ของทั้งสองทีมจากค่า PPDA, Possession, Directness
2. ใช้ผลการจำลองแมตช์ (Simulation) มาประกอบการฟันธง
3. เขียนทำนายผลสรุป

ตอบเป็นภาษาไทย สไตล์ตื่นเต้น เจาะลึก
'''
    
    # 8. Call Gemini
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(API_URL, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        if response.status_code == 200:
            print(prompt) # Print prompt for debugging
            print("\n" + "="*50)
            print(response.json()['candidates'][0]['content']['parts'][0]['text'])
            print("="*50 + "\n")
        else:
            print(f"API Error: {response.text}")
            # Fallback output
            print(sim_result)
    except Exception as e:
        print(f"Error: {e}")
        print(sim_result)

if __name__ == "__main__":
    main()
