import pandas as pd
import sys
import os
import requests
import json
# import simulator # Legacy simulator removed

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "AIzaSyAIkLd916V-iQua89t3stHYtkwOLBXu8Us"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"

def find_team_league(team_name):
    # Check sofaplayer directories to identify league
    base_dir = "sofaplayer"
    # Try both original name and normalized name
    search_names = [team_name, normalize_team_name(team_name)]
    for league in os.listdir(base_dir):
        league_path = os.path.join(base_dir, league)
        if os.path.isdir(league_path):
            for file in os.listdir(league_path):
                for sn in search_names:
                    if sn in file:
                        return league
    return None

def normalize_team_name(name):
    """Normalizes team names to match SofaScore/FBref differences."""
    mapping = {
        "Paris S-G": "Paris Saint-Germain",
        "PSG": "Paris Saint-Germain",
        "Rennes": "Stade Rennais",
        "Lyon": "Olympique Lyonnais",
        "Marseille": "Olympique de Marseille",
        "Monaco": "AS Monaco",
        "Nice": "OGC Nice",
        "Lille": "LOSC Lille",
        "Brest": "Stade Brestois",
        "Man Utd": "Manchester United",
        "Manchester Utd": "Manchester United",
        "Sheffield Utd": "Sheffield United",
        "Nott'm Forest": "Nottingham Forest",
        "Wolves": "Wolverhampton",
        "Brighton": "Brighton & Hove Albion"
    }
    return mapping.get(name, name)

def get_game_flow_stats(team_name, league):
    try:
        filename = f'game flow/{league}_GameFlow.xlsx'
        if os.path.exists(filename):
            df = pd.read_excel(filename)
            # Use normalized name for search
            search_name = normalize_team_name(team_name)
            
            # Try exact match first (normalized)
            row = df[df['Team_Name'].str.contains(search_name, case=False, na=False)]
            
            # If not found, try original name
            if row.empty:
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
            
            search_name = normalize_team_name(team_name)
            
            row = df[df['Squad'].str.contains(search_name, case=False, na=False)]
            
            # Fallback
            if row.empty:
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
            
            # Use normalized name
            search_name = normalize_team_name(team_name)
            
            row = df[df['Team_Name'].str.contains(search_name, case=False, na=False)]
            
            if row.empty:
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
        # Try both original and normalized names for file lookup
        search_names = [team_name, normalize_team_name(team_name)]
        
        filename = None
        for sn in search_names:
            candidate = f"sofaplayer/{league}/{sn}_stats.xlsx"
            if os.path.exists(candidate):
                filename = candidate
                break
        
        # If still not found, scan directory
        if not filename:
            for f in os.listdir(f"sofaplayer/{league}"):
                for sn in search_names:
                    if sn in f:
                        filename = f"sofaplayer/{league}/{f}"
                        break
                if filename:
                    break
        
        if filename and os.path.exists(filename):
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

def get_team_quality_stats(league, home_team, away_team):
    """
    Loads advanced team quality stats (Rating, Errors, etc.) from sofascore_team_data.
    """
    try:
        file_path = f"sofascore_team_data/{league}_Team_Stats.xlsx"
        if not os.path.exists(file_path):
            print(f"[Warning] Team Stats file not found: {file_path}")
            return None, None
            
        df = pd.read_excel(file_path)
        
        # Fuzzy match or direct match? Let's try direct first, then simple containment
        def find_team_row(team_name):
            row = df[df['Team_Name'] == team_name]
            if row.empty:
                # Try partial match
                row = df[df['Team_Name'].str.contains(team_name, case=False, na=False)]
            return row

        h_row = find_team_row(home_team)
        a_row = find_team_row(away_team)
        
        if h_row.empty or a_row.empty:
            print(f"[Warning] Could not find stats for {home_team} or {away_team} in {file_path}")
            return None, None
            
        # Extract relevant columns
        cols = ['avgRating', 'errorsLeadingToGoal', 'possessionLost', 'goalsScored', 'goalsConceded']
        
        h_qual = h_row[cols].iloc[0].to_dict()
        a_qual = a_row[cols].iloc[0].to_dict()
        
        return h_qual, a_qual
        
    except Exception as e:
        print(f"[Error] loading team quality stats: {e}")
        return None, None

def main():
    if len(sys.argv) < 3:
        print("Usage: python analyze_match.py <HomeTeam> <AwayTeam>")
        return

    home = sys.argv[1]
    away = sys.argv[2]
    
    print(f"กำลังวิเคราะห์ {home} vs {away}...")
    
    # 1. Detect League
    league = find_team_league(home)
    if not league:
        # Try finding away team
        league = find_team_league(away)
    
    if not league:
        print(f"ไม่สามารถตรวรจสอบลีกของ {home} หรือ {away} ได้โดยอัตโนมัติ")
        # Default fallback or exit? let's try Premier_League if fails but warn
        print("กำลังใช้ค่าเริ่มต้นเป็น Premier_League (คำเตือน!)")
        league = "Premier_League"
    else:
        print(f"ลีกที่ตรวจสอบพบ: {league}")

    # 2. Gather Data
    h_flow = get_game_flow_stats(home, league)
    a_flow = get_game_flow_stats(away, league)
    h_squad = get_squad_stats(home, league)
    a_squad = get_squad_stats(away, league)
    h_sim = get_simulation_stats(home, league)
    a_sim = get_simulation_stats(away, league)
    h_top, h_scorers = get_top_players(home, league)
    a_top, a_scorers = get_top_players(away, league)
    h_qual, a_qual = get_team_quality_stats(league, home, away) # New call

    # Safe formatting helper
    def safe_fmt(val, fmt=".2f"):
        try:
            return f"{float(val):{fmt}}"
        except (ValueError, TypeError):
            return str(val)

    # 3. Simulation v7.0 (Winner Mentality)
    print("Running Simulator v7.0 (Winner Mentality)...")
    import xg_engine
    import simulator_v7
    
    eng = xg_engine.XGEngine(league)
    h_xg = eng.get_team_rolling_stats(home, n_games=10)
    a_xg = eng.get_team_rolling_stats(away, n_games=10)
    
    sim_str = ""
    if h_xg and a_xg:
        sim = simulator_v7.simulate_match(h_xg, a_xg, h_sim, a_sim, iterations=10000)
        
        # Determine confidence based on probability spread
        win_prob = max(sim['home_win_prob'], sim['away_win_prob'])
        confidence = "สูง (High)" if win_prob > 60 else "ปานกลาง (Medium)" if win_prob > 45 else "ต่ำ (Low)"
        
        sim_str = f"""
        **ผลการจำลอง 10,000 นัด (Simulator v7.0 - Winner Mentality Edition):**
        *   **{home} ชนะ:** {sim['home_win_prob']:.1f}% (ExpG: {sim['expected_goals_home']:.2f})
        *   **เสมอ:** {sim['draw_prob']:.1f}%
        *   **{away} ชนะ:** {sim['away_win_prob']:.1f}% (ExpG: {sim['expected_goals_away']:.2f})
        *   **สกอร์ที่คาด:** {sim['most_likely_score']}
        *   **3 สกอร์ที่โมเดลเชื่อมั่นสูงสุด:** {sim['top3_scores']}
        *   **Bonus Applied:** {sim['bonus_applied']} (Boost for Superior Team)
        *   **ความมั่นใจ:** {confidence}
        
        **สถิติเชิงลึก (Dual Data Sources - 10 นัดล่าสุด):**
        *   **{home}:** xG For {h_xg['attack']['xg_per_game']:.2f}/เกม | xGA {h_xg['defense']['xga_per_game']:.2f}/เกม | Goals/90: {safe_fmt(h_sim.get('goals_scored_per_game', 'N/A') if h_sim else 'N/A')} | Conceded/90: {safe_fmt(h_sim.get('goals_conceded_per_game', 'N/A') if h_sim else 'N/A')}
        *   **{away}:** xG For {a_xg['attack']['xg_per_game']:.2f}/เกม | xGA {a_xg['defense']['xga_per_game']:.2f}/เกม | Goals/90: {safe_fmt(a_sim.get('goals_scored_per_game', 'N/A') if a_sim else 'N/A')} | Conceded/90: {safe_fmt(a_sim.get('goals_conceded_per_game', 'N/A') if a_sim else 'N/A')}
        """
    else:
        print("Could not retrieve xG stats. Falling back to basic simulation.")
        # Fallback to old logic if needed, but for now just warn
        sim_str = "**Warning:** xG Data not available. Simulation skipped."

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
    *   **{home}:** PPDA {safe_fmt(h_flow.get('calc_PPDA', 'N/A'))}, การครองบอล (Possession) {h_squad.get('Poss', 'N/A')}%, ประตู/90นาที {h_squad.get('Per 90 Minutes_Gls', 'N/A')}, ผู้เล่นหลัก: {', '.join(h_top)}, ดาวซัลโว: {', '.join(h_scorers)}
    *   **{away}:** PPDA {safe_fmt(a_flow.get('calc_PPDA', 'N/A'))}, การครองบอล (Possession) {a_squad.get('Poss', 'N/A')}%, ประตู/90นาที {a_squad.get('Per 90 Minutes_Gls', 'N/A')}, ผู้เล่นหลัก: {', '.join(a_top)}, ดาวซัลโว: {', '.join(a_scorers)}
    
    {sim_str}
    
    **ข้อมูลสถานการณ์ปัจจุบัน (Live Context & News):**
    {live_context}

    ================================================================================
    **ส่วนที่ 1: การวิเคราะห์ภาพรวมทีม (Team Overview Analysis)**
    *ในส่วนนี้ให้วิเคราะห์ภาพรวมของทั้งสองทีม*
    ================================================================================
    1.  **สภาพทีม & ข่าวล่าสุด (Team News):**
        *   สรุปจาก Live Context (ตัวเจ็บ/แบน/ไลน์อัพ) และผลกระทบ
    2.  **การวิเคราะห์เชิงกลยุทธ์ & แทคติก (Strategic & Tactical):**
        *   วิเคราะห์การปะทะกันของ PPDA และสไตล์การเล่น
        *   วิเคราะห์การครองบอล (Possesion) ใครจะเป็นฝ่ายครองเกม?
    3.  **ตารางเปรียบเทียบกลยุทธ์ (Strategic Comparison Table):**
        *   สร้างตารางเปรียบเทียบค่าสำคัญ: PPDA, การครองบอล (Possession), ประตูที่ทำได้ (Goals Scored), ประตูที่เสีย (Goals Conceded)
        *   เพิ่มคอลัมน์ "คำอธิบาย/ผลกระทบ" (Explanation) ว่าค่าที่ต่างกันนี้จะส่งผลต่อรูปเกมอย่างไร เช่น "PPDA ต่ำกว่า = เพรสซิ่งหนักกว่า"
    4.  **ภาพรวมและแนวโน้ม (Overview & Trends):**
        *   วิเคราะห์ H2H และฟอร์มล่าสุด (จาก Live Context)
    5.  **บทสรุปภาพรวม (Match Summary):**
        *   ฟันธงรูปเกมและสกอร์ที่คาดการณ์ (ผสมผสานผลจำลอง Simulation กับ Context)

    ================================================================================
    **ส่วนที่ 2: การวิเคราะห์ผู้เล่นรายบุคคล (Player Analysis)**
    *ในส่วนนี้ให้เจาะลึกรายบุคคล*
    ================================================================================
    1.  **เจาะลึกผู้เล่นหลัก (Key Player Deep Dive):**
        *   วิเคราะห์ฟอร์มและบทบาทของคีย์แมน (Top Rated/Scorers)
    2.  **ดวลกันตัวต่อตัว (Key Battle):**
        *   วิเคราะห์การดวลกันเฉพาะจุดที่น่าสนใจ
    3.  **ตัวทีเด็ด (X-Factor):**
        *   ผู้เล่นที่อาจเป็นตัวตัดสินเกม (Game Changer)

    **Tone:** มืออาชีพ, ลึกซึ้ง, ใช้ภาษาฟุตบอลที่สละสลวย
    """

    # 6. Gemini
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
            if response.status_code == 200:
                text_content = response.json()['candidates'][0]['content']['parts'][0]['text']
                print(text_content)
                
                # Save to Markdown file
                filename = f"analysis_{home}_{away}.md"
                with open(filename, "w", encoding='utf-8') as f:
                    f.write(text_content)
                print(f"\n[Info] Full analysis saved to '{filename}'")
                break
            elif response.status_code == 429:
                print(f"Rate limit hit. Retrying in {2**attempt} seconds...")
                time.sleep(2**attempt)
            else:
                print(f"API Error: {response.text}")
                break
        except Exception as e:
            print(f"Error: {e}")
            break

    # 7. Save to latest_prediction.json
    try:
        if 'sim' in locals():
            # Determine predicted result
            if sim['home_win_prob'] > sim['away_win_prob'] and sim['home_win_prob'] > sim['draw_prob']:
                pred_res = "Home"
            elif sim['away_win_prob'] > sim['home_win_prob'] and sim['away_win_prob'] > sim['draw_prob']:
                pred_res = "Away"
            else:
                pred_res = "Draw"

            prediction_data = {
                "Date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                "Match": f"{home} vs {away}",
                "League": league,
                "Home_Team": home,
                "Away_Team": away,
                "Pred_Home_Win": sim['home_win_prob'],
                "Pred_Draw": sim['draw_prob'],
                "Pred_Away_Win": sim['away_win_prob'],
                "Pred_Score": sim['most_likely_score'],
                "Pred_Result": pred_res
            }
            
            with open("latest_prediction.json", "w", encoding='utf-8') as f:
                json.dump(prediction_data, f, indent=4, ensure_ascii=False)
            print(f"\n[Info] Prediction saved to 'latest_prediction.json'. Run 'savepredic' to add to tracker.")
    except Exception as e:
        print(f"Error saving prediction JSON: {e}")

if __name__ == "__main__":
    main()
