
import pandas as pd
import sys
import os
import requests
import json
import simulator

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "AIzaSyBuBznv-XRM-Q7ThdTq_dlO8Z78UyN3r60"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"

def get_game_flow_stats(team_name):
    try:
        df = pd.read_excel('game flow/Premier_League_GameFlow.xlsx')
        # Fuzzy match
        row = df[df['Team_Name'].str.contains(team_name, case=False, na=False)]
        if not row.empty:
            return row.iloc[0].to_dict()
    except Exception as e:
        print(f"Error reading game flow for {team_name}: {e}")
    return {}

def get_squad_stats(team_name):
    try:
        df = pd.read_excel('all stats/Premier_League_Stats.xlsx')
        # Fuzzy match
        row = df[df['Squad'].str.contains(team_name, case=False, na=False)]
        if not row.empty:
            return row.iloc[0].to_dict()
    except Exception as e:
        print(f"Error reading squad stats for {team_name}: {e}")
    return {}

def get_top_players(team_name, top_n=3):
    try:
        # File name might differ slightly, e.g. "Manchester City_stats.xlsx"
        filename = f"sofaplayer/Premier_League/{team_name}_stats.xlsx"
        if not os.path.exists(filename):
             # Try listing dir to find match
             for f in os.listdir("sofaplayer/Premier_League"):
                 if team_name in f:
                     filename = f"sofaplayer/Premier_League/{f}"
                     break
        
        df = pd.read_excel(filename)
        
        # Sort by Rating
        top_rated = df.sort_values(by='rating', ascending=False).head(top_n)
        top_scorers = df.sort_values(by='goals', ascending=False).head(top_n)
        
        players_info = []
        for i in range(top_n):
            p = top_rated.iloc[i]
            players_info.append(f"{p['Player_Name']} (Rating: {p['rating']})")
            
        return players_info, top_scorers['Player_Name'].tolist()
    except Exception as e:
        print(f"Error reading player stats for {team_name}: {e}")
        return [], []

def get_simulation_stats(team_name):
    # Load from SofaScore Team Data which has goalsConceded
    try:
        df = pd.read_excel('sofascore_team_data/Premier_League_Team_Stats.xlsx')
        # Fuzzy match
        row = df[df['Team_Name'].str.contains(team_name, case=False, na=False)]
        if not row.empty:
            return {
                'goals_scored_per_game': row.iloc[0]['goalsScored_per_90'],
                'goals_conceded_per_game': row.iloc[0]['goalsConceded_per_90']
            }
    except Exception as e:
        print(f"Error reading simulation stats for {team_name}: {e}")
    return None

def get_league_averages():
    try:
        df = pd.read_excel('sofascore_team_data/Premier_League_Team_Stats.xlsx')
        avg_scored = df['goalsScored_per_90'].mean()
        # Approx home advantage: Home teams score 10% more on average
        return {
            'avg_goals_home': avg_scored * 1.1, 
            'avg_goals_away': avg_scored * 0.9
        }
    except:
        return {'avg_goals_home': 1.5, 'avg_goals_away': 1.2}

def main():
    home = "Liverpool"
    away = "Manchester City"
    
    print(f"Gathering comprehensive data for {home} vs {away}...")
    
    # 1. Game Flow
    h_flow = get_game_flow_stats(home)
    a_flow = get_game_flow_stats(away)
    
    # 2. Squad Stats
    h_squad = get_squad_stats(home)
    a_squad = get_squad_stats(away)
    
    # 3. Player Stats
    h_top_rated, h_scorers = get_top_players(home)
    a_top_rated, a_scorers = get_top_players(away)
    
    # 4. Simulation
    h_sim_stats = get_simulation_stats(home)
    a_sim_stats = get_simulation_stats(away)
    league_avgs = get_league_averages()
    
    sim_result_str = ""
    if h_sim_stats and a_sim_stats:
        sim_data = simulator.simulate_match(home, away, h_sim_stats, a_sim_stats, league_avgs, iterations=300)
        sim_result_str = f"""
        **ผลการจำลอง 300 นัด (300 Match Simulation):**
        - {home} ชนะ: {sim_data['home_win_prob']:.1f}%
        - เสมอ: {sim_data['draw_prob']:.1f}%
        - {away} ชนะ: {sim_data['away_win_prob']:.1f}%
        - สกอร์ที่น่าจะเกิดขึ้นที่สุด: {sim_data['most_likely_score']}
        """

    # 5. Construct Prompt with TEMPLATE STRUCTURE
    prompt = f"""
    คุณคือนักวิเคราะห์ฟุตบอลระดับโลก. จงเขียนรายงานการวิเคราะห์การแข่งขันระหว่าง **{home}** vs **{away}** 
    โดย **ต้องแยกส่วนการแสดงผล** ให้ตรงกับ 2 หัวข้อหลักนี้อย่างชัดเจน:

    **ข้อมูลที่ถูกต้อง (Verified Data Base):**
    *   **Liverpool:** PPDA 4.88, Possession 61.6%, Goals/90 1.58, Key Men: Salah, Wirtz, Ekitike (8 Goals)
    *   **Man City:** PPDA 5.66, Possession 59.6%, Goals/90 1.92, Key Men: Haaland (20 Goals), Foden, Semenyo
    *   **Team News:** Liverpool ขาด Frimpong/Bradley, Man City ขาด Stones/Gvardiol/Dias
    
    {sim_result_str}

    ================================================================================
    **SECTION 1: {{@ตัวอย่างการวิเคราะห์ภาพรวมทีม}} (Team Overview Analysis)**
    *ในส่วนนี้ให้วิเคราะห์ภาพรวมของทั้งสองทีม*
    ================================================================================
    1.  **สภาพทีม & ข่าวล่าสุด (Team News):**
        *   ระบุตัวเจ็บและการปรับทัพ (เน้นวิกฤตกองหลัง City vs แบ็ค Liverpool)
    2.  **การวิเคราะห์เชิงกลยุทธ์ & แทคติก (Strategic & Tactical):**
        *   วิเคราะห์การปะทะกันของ PPDA (4.88 vs 5.66) และสไตล์การเล่น
        *   วิเคราะห์ Field Tilt และ Possession ใครจะเป็นฝ่ายครองเกม?
    3.  **ภาพรวมและแนวโน้ม (Overview & Trends):**
        *   วิเคราะห์ H2H และฟอร์มล่าสุด
    4.  **บทสรุปภาพรวม (Match Summary):**
        *   ฟันธงรูปเกมและสกอร์ที่คาดการณ์

    ================================================================================
    **SECTION 2: {{@ตัวอย่างการวิเคราะหืผู้เล่นในทีม}} (Player Analysis)**
    *ในส่วนนี้ให้เจาะลึกรายบุคคล*
    ================================================================================
    1.  **Key Player Deep Dive:**
        *   วิเคราะห์ฟอร์มและบทบาทของคีย์แมน (Haaland, Ekitike, Salah, Foden) พร้อมสถิติประกอบ (ประตูล่าสุด/เรตติ้ง)
    2.  **Key Battle (จุดปะทะสำคัญ):**
        *   วิเคราะห์การดวลกันเฉพาะจุด เช่น **Wirtz vs Khusanov** หรือ **Salah vs Gvardiol**
    3.  **X-Factor (ตัวทีเด็ด):**
        *   ผู้เล่นที่อาจเป็นตัวตัดสินเกม (Game Changer)

    **Tone:** มืออาชีพ, ลึกซึ้ง, ใช้ภาษาฟุตบอลที่สละสลวย
    """
    
    # 5. Call Gemini
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(API_URL, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        if response.status_code == 200:
            print("\n" + "="*50)
            print(response.json()['candidates'][0]['content']['parts'][0]['text'])
            print("="*50 + "\n")
        else:
            print(f"API Error: {response.text}")
    except Exception as e:
        print(f"Error calling API: {e}")

if __name__ == "__main__":
    main()
