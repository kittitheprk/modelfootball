import pandas as pd
import os
import requests
import json
import sys

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={API_KEY}"

def get_match_context(home, away):
    """Tries to find the analysis markdown file for context."""
    # Try common formats
    files = [
        os.path.join("analyses", f"analysis_{home}_{away}.md"),
        os.path.join("analyses", f"analysis_{home} vs {away}.md"),
        f"analysis_{home}_{away}.md",
        f"analysis_{home} vs {away}.md",
    ]
    
    # Also check directory scan if needed, but linear check is fast
    for f_name in files:
        if os.path.exists(f_name):
            try:
                with open(f_name, "r", encoding="utf-8") as f:
                    return f.read()[:2000] # Limit context to save tokens, first 2k chars usually has summary/stats
            except:
                pass
    return "No detailed analysis file found."

def analyze_with_ai(match_info, context):
    """Sends data to Gemini to decide the best bet."""
    if not API_KEY:
        return None
    
    prompt = f"""
    คุณคือเซียนวิเคราะห์บอลขั้นเทพ (Professional Football Bettor). 
    จงวิเคราะห์ข้อมูลต่อไปนี้เพื่อหา **"ตัวเลือกการลงทุนที่ดีที่สุด (Best Bet)"** เพียง 1 ตัวเลือกสำหรับคู่นี้.
    
    **ข้อมูลการแข่งขัน:**
    - Match: {match_info['Match']}
    - Date: {match_info['Date']}
    
    **สถิติความน่าจะเป็นจากระบบ (Model Probabilities %):**
    {json.dumps(match_info['Stats'], indent=2, ensure_ascii=False)}
    
    **บริบทและบทวิเคราะห์ก่อนหน้า (Context):**
    {context}
    
    **คำสั่ง (Instruction):**
    1.  วิเคราะห์ความสอดคล้องระหว่าง "ตัวเลข (Model)" กับ "บริบท (Context)".
        - ถ้าตัวเลขสูงแต่บริบทแย่ (เช่น ตัวหลักเจ็บ) -> ให้เลือกทางที่ปลอดภัยกว่า
        - ถ้าตัวเลขสอดคล้องกับบริบท -> ให้เลือกตัวเลือกนั้น
    2.  เปรียบเทียบ Handicap (HDP) กับ Over/Under (O/U).
        - อันไหนเสี่ยงน้อยกว่า? อันไหนมีโอกาสชนะเดิมพันสูงกว่า?
    3.  **ฟันธง (Decision):** เลือกมา 1 อย่างที่มั่นใจที่สุด (เช่น "Home Win", "Over 2.5", "Handicap Away +1")
    4.  **ความมั่นใจ (Confidence):** สูง (High), ปานกลาง (Medium), ต่ำ (Low)
    5.  **เหตุผล (Reasoning):** อธิบายสั้นๆ ว่าทำไมถึงเลือกตัวนี้ (พิจารณาทั้งตัวเลขและปัจจัยแวดล้อม)

    **รูปแบบการตอบ (Response Format JSON ONLY):**
    {{
        "Selected_Bet": "ชื่อตัวเลือกที่เลือก",
        "Confidence": "ระดับความมั่นใจ",
        "Reasoning": "เหตุผลประกอบการตัดสินใจ"
    }}
    ตอบเป็น JSON เท่านั้น ไม่ต้องมีเกริ่นนำ
    """
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(
            API_URL,
            headers={'Content-Type': 'application/json'},
            data=json.dumps(payload),
            timeout=60
        )
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"API Error: {response.text}")
            return None
    except Exception as e:
        print(f"Request Error: {e}")
        return None

def main():
    filename = "prediction_tracker.xlsx"
    if not os.path.exists(filename):
        print(f"{filename} not found.")
        return
    if not API_KEY:
        print("[Warning] GEMINI_API_KEY not set. Skipping AI best-bet analysis.")
        return

    print("Reading 'bet data'...")
    try:
        df_bet = pd.read_excel(filename, sheet_name='bet data')
    except ValueError:
        print("'bet data' sheet not found.")
        return

    # Load existing Predictions to avoid re-analyzing
    try:
        df_existing = pd.read_excel(filename, sheet_name='bet predic')
        existing_matches = set(zip(df_existing['Date'], df_existing['Match']))
        print(f"Found {len(existing_matches)} existing analyses in 'bet predic'.")
    except (ValueError, KeyError):
        df_existing = pd.DataFrame(columns=['Date', 'Match', 'Selected_Bet', 'Confidence', 'Reasoning'])
        existing_matches = set()
        print("'bet predic' sheet not found or empty. Creating new.")

    check_list = []
    
    # Prepare data for AI (Only NEW matches)
    new_count = 0
    for index, row in df_bet.iterrows():
        match_key = (row['Date'], row['Match'])
        
        # Skip if already exists
        if match_key in existing_matches:
            continue
            
        new_count += 1
        # filter only numeric prob columns
        stats = {k: v for k, v in row.items() if k not in ['Date', 'Match', 'League'] and isinstance(v, (int, float))}
        
        match_data = {
            'Match': row['Match'],
            'Date': row['Date'],
            'Stats': stats
        }
        check_list.append(match_data)

    if new_count == 0:
        print("No new matches to analyze. 'bet predic' is up to date.")
        return

    results = []

    print(f"Analyzing {new_count} NEW matches with AI...")
    
    for item in check_list:
        home, away = item['Match'].split(' vs ')
        print(f"Processing: {item['Match']}...", end=" ")
        
        # Get context
        context = get_match_context(home, away)
        
        # Call AI
        ai_resp = analyze_with_ai(item, context)
        
        if ai_resp:
            # Clean JSON string if needed (sometimes Gemini wraps in ```json ... ```)
            clean_resp = ai_resp.replace('```json', '').replace('```', '').strip()
            try:
                decision = json.loads(clean_resp)
                
                results.append({
                    'Date': item['Date'],
                    'Match': item['Match'],
                    'Selected_Bet': decision.get('Selected_Bet', 'Error'),
                    'Confidence': decision.get('Confidence', 'Unknown'),
                    'Reasoning': decision.get('Reasoning', 'Parse Error')
                })
                print("Done.")
            except json.JSONDecodeError:
                print("JSON Error. Raw response:", clean_resp)
        else:
            print("Failed.")
            
    # Save to 'bet predic' sheet (Append)
    if results:
        df_new = pd.DataFrame(results)
        # Combine with existing
        df_final = pd.concat([df_existing, df_new], ignore_index=True)
        
        with pd.ExcelWriter(filename, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_final.to_excel(writer, sheet_name='bet predic', index=False)
            
        print("\n" + "="*50)
        print(f"Analysis Complete! Added {len(results)} new predictions to 'bet predic'.")
        print("="*50)
        print(df_new[['Match', 'Selected_Bet', 'Confidence']].to_string())

if __name__ == "__main__":
    main()
