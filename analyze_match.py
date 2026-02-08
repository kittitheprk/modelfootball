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

def find_team_league(team_name):
    # Check sofaplayer directories to identify league
    base_dir = "sofaplayer"
    for league in os.listdir(base_dir):
        league_path = os.path.join(base_dir, league)
        if os.path.isdir(league_path):
            for file in os.listdir(league_path):
                if team_name in file:
                    return league
    return None

def get_game_flow_stats(team_name, league):
    try:
        filename = f'game flow/{league}_GameFlow.xlsx'
        if os.path.exists(filename):
            df = pd.read_excel(filename)
            row = df[df['Team_Name'].str.contains(team_name, case=False, na=False)]
            if not row.empty:
                return row.iloc[0].to_dict()
    except Exception as e:
        print(f"Error reading game flow for {team_name}: {e}")
    return {}

def get_squad_stats(team_name, league):
    try:
        filename = f'all stats/{league}_Stats.xlsx'
        if os.path.exists(filename):
            df = pd.read_excel(filename)
            row = df[df['Squad'].str.contains(team_name, case=False, na=False)]
            if not row.empty:
                return row.iloc[0].to_dict()
    except Exception as e:
        print(f"Error reading squad stats for {team_name}: {e}")
    return {}

def get_simulation_stats(team_name, league):
    try:
        filename = f'sofascore_team_data/{league}_Team_Stats.xlsx'
        if os.path.exists(filename):
            df = pd.read_excel(filename)
            row = df[df['Team_Name'].str.contains(team_name, case=False, na=False)]
            if not row.empty:
                return {
                    'goals_scored_per_game': row.iloc[0]['goalsScored_per_90'],
                    'goals_conceded_per_game': row.iloc[0]['goalsConceded_per_90']
                }
    except Exception as e:
        print(f"Error reading sim stats for {team_name}: {e}")
    return None

def get_league_averages(league):
    try:
        filename = f'sofascore_team_data/{league}_Team_Stats.xlsx'
        if os.path.exists(filename):
            df = pd.read_excel(filename)
            avg_scored = df['goalsScored_per_90'].mean()
            return {'avg_goals_home': avg_scored * 1.1, 'avg_goals_away': avg_scored * 0.9}
    except:
        pass
    return {'avg_goals_home': 1.5, 'avg_goals_away': 1.2}

def get_top_players(team_name, league, top_n=3):
    try:
        # File name might differ slightly, e.g. "Manchester City_stats.xlsx"
        filename = f"sofaplayer/{league}/{team_name}_stats.xlsx"
        if not os.path.exists(filename):
             # Try listing dir to find match
             for f in os.listdir(f"sofaplayer/{league}"):
                 if team_name in f:
                     filename = f"sofaplayer/{league}/{f}"
                     break
        
        if os.path.exists(filename):
            df = pd.read_excel(filename)
            top_rated = df.sort_values(by='rating', ascending=False).head(top_n)
            top_scorers = df.sort_values(by='goals', ascending=False).head(top_n)
            
            players_info = []
            for i in range(len(top_rated)):
                p = top_rated.iloc[i]
                players_info.append(f"{p['Player_Name']} (Rating: {p['rating']})")
                
            return players_info, top_scorers['Player_Name'].tolist()
    except Exception as e:
        print(f"Error reading player stats for {team_name}: {e}")
    return [], []

def main():
    if len(sys.argv) < 3:
        print("Usage: python analyze_match.py <HomeTeam> <AwayTeam>")
        return

    home = sys.argv[1]
    away = sys.argv[2]
    
    print(f"Analyzing {home} vs {away}...")
    
    # 1. Detect League
    league = find_team_league(home)
    if not league:
        # Try finding away team
        league = find_team_league(away)
    
    if not league:
        print(f"Could not automatically detect league for {home} or {away}")
        # Default fallback or exit? let's try Premier_League if fails but warn
        print("Defaulting to Premier_League (Warning!)")
        league = "Premier_League"
    else:
        print(f"Detected League: {league}")

    # 2. Gather Data
    h_flow = get_game_flow_stats(home, league)
    a_flow = get_game_flow_stats(away, league)
    h_squad = get_squad_stats(home, league)
    a_squad = get_squad_stats(away, league)
    h_sim = get_simulation_stats(home, league)
    a_sim = get_simulation_stats(away, league)
    h_top, h_scorers = get_top_players(home, league)
    a_top, a_scorers = get_top_players(away, league)

    # 3. Simulation
    sim_str = ""
    if h_sim and a_sim:
        avgs = get_league_averages(league)
        sim = simulator.simulate_match(home, away, h_sim, a_sim, avgs, iterations=300)
        sim_str = f"""
        **ผลการจำลอง 300 นัด (Simulation):**
        - {home} ชนะ: {sim['home_win_prob']:.1f}%
        - เสมอ: {sim['draw_prob']:.1f}%
        - {away} ชนะ: {sim['away_win_prob']:.1f}%
        - สกอร์ที่น่าจะเกิดขึ้นที่สุด: {sim['most_likely_score']}
        """

    # 4. Context (Live Data)
    context_file = "match_context.txt"
    live_context = ""
    if os.path.exists(context_file):
        with open(context_file, "r", encoding="utf-8") as f:
            live_context = f.read()
    else:
        live_context = "No live context available (Lineups/Injuries missing)."

    # 5. Prompt
    prompt = f"""
    คุณคือนักวิเคราะห์ฟุตบอลระดับโลก. จงเขียนรายงานการวิเคราะห์การแข่งขันระหว่าง **{home}** vs **{away}** 
    โดย **ต้องแยกส่วนการแสดงผล** ให้ตรงกับ 2 หัวข้อหลักนี้อย่างชัดเจน:

    **ข้อมูลที่ถูกต้อง (Verified Data Base):**
    *   **{home}:** PPDA {h_flow.get('calc_PPDA', 'N/A'):.2f}, Possession {h_squad.get('Poss', 'N/A')}%, Goals/90 {h_squad.get('Per 90 Minutes_Gls', 'N/A')}, Key Men: {', '.join(h_top)}, Top Scorers: {', '.join(h_scorers)}
    *   **{away}:** PPDA {a_flow.get('calc_PPDA', 'N/A'):.2f}, Possession {a_squad.get('Poss', 'N/A')}%, Goals/90 {a_squad.get('Per 90 Minutes_Gls', 'N/A')}, Key Men: {', '.join(a_top)}, Top Scorers: {', '.join(a_scorers)}
    
    {sim_str}
    
    **ข้อมูลสถานการณ์ปัจจุบัน (Live Context & News):**
    {live_context}

    ================================================================================
    **SECTION 1: {{@ตัวอย่างการวิเคราะห์ภาพรวมทีม}} (Team Overview Analysis)**
    *ในส่วนนี้ให้วิเคราะห์ภาพรวมของทั้งสองทีม*
    ================================================================================
    1.  **สภาพทีม & ข่าวล่าสุด (Team News):**
        *   สรุปจาก Live Context (ตัวเจ็บ/แบน/ไลน์อัพ) และผลกระทบ
    2.  **การวิเคราะห์เชิงกลยุทธ์ & แทคติก (Strategic & Tactical):**
        *   วิเคราะห์การปะทะกันของ PPDA และสไตล์การเล่น
        *   วิเคราะห์ Possesion ใครจะเป็นฝ่ายครองเกม?
    3.  **ตารางเปรียบเทียบกลยุทธ์ (Strategic Comparison Table):**
        *   สร้างตารางเปรียบเทียบค่าสำคัญ: PPDA, Possession, Goals Scored, Goals Conceded
        *   เพิ่มคอลัมน์ "คำอธิบาย/ผลกระทบ" (Explanation) ว่าค่าที่ต่างกันนี้จะส่งผลต่อรูปเกมอย่างไร เช่น "PPDA ต่ำกว่า = เพรสซิ่งหนักกว่า"
    4.  **ภาพรวมและแนวโน้ม (Overview & Trends):**
        *   วิเคราะห์ H2H และฟอร์มล่าสุด (จาก Live Context)
    5.  **บทสรุปภาพรวม (Match Summary):**
        *   ฟันธงรูปเกมและสกอร์ที่คาดการณ์ (ผสมผสาน Simulation กับ Context)

    ================================================================================
    **SECTION 2: {{@ตัวอย่างการวิเคราะหืผู้เล่นในทีม}} (Player Analysis)**
    *ในส่วนนี้ให้เจาะลึกรายบุคคล*
    ================================================================================
    1.  **Key Player Deep Dive:**
        *   วิเคราะห์ฟอร์มและบทบาทของคีย์แมน (Top Rated/Scorers)
    2.  **Key Battle (จุดปะทะสำคัญ):**
        *   วิเคราะห์การดวลกันเฉพาะจุดที่น่าสนใจ
    3.  **X-Factor (ตัวทีเด็ด):**
        *   ผู้เล่นที่อาจเป็นตัวตัดสินเกม (Game Changer)

    **Tone:** มืออาชีพ, ลึกซึ้ง, ใช้ภาษาฟุตบอลที่สละสลวย
    """

    # 6. Gemini
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(API_URL, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        if response.status_code == 200:
            print(response.json()['candidates'][0]['content']['parts'][0]['text'])
        else:
            print(f"API Error: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
