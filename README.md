# ระบบวิเคราะห์และทำนายผลฟุตบอล (Simulator v9)

โปรเจกต์นี้ใช้ข้อมูลทีม, ผู้เล่น, และแมตช์ย้อนหลังจากหลายแหล่ง เพื่อคำนวณความน่าจะเป็นผลการแข่งขัน, สกอร์ที่เป็นไปได้, และสร้างรายงานวิเคราะห์ก่อนแข่ง โดยโฟลว์หลักคือ `analyze_match.py` + `simulator_v9.py`.

## ความสามารถหลัก

- โมเดลหลัก `simulator_v9.py` (Poisson + Dixon-Coles + player-aware adjustments)
- Dynamic Lineup Strength จากรายชื่อนักเตะจริง/คาดการณ์
- Key Matchups ตามตำแหน่ง (ริมเส้น/ตัวกลาง)
- Fatigue Analysis จากความถี่การลงแข่ง
- xT / progression proxy จาก Match Logs + Team Stats
- สรุปโอกาสเดิมพัน HDP และ Over/Under ใน `latest_prediction.json`

## โครงสร้างไฟล์สำคัญ

```text
.
├─ analyze_match.py                 # สคริปต์หลักสำหรับวิเคราะห์แมตช์
├─ simulator_v9.py                 # โมเดลล่าสุด (lineup + matchup + fatigue + progression)
├─ simulator_v8.py                 # โมเดล baseline รุ่นก่อน
├─ xg_engine.py                    # rolling xG/xGA + form จาก Match Logs
├─ update_tracker.py               # บันทึก prediction/สรุปผลลง Excel tracker
├─ scripts/
│  ├─ run_update.py                # pipeline อัปเดตข้อมูลแบบ headless
│  └─ system_check.py              # ตรวจสุขภาพระบบและ preflight
├─ match_context.txt               # context ก่อนแข่ง (ไลน์อัป/ข่าวทีม)
├─ latest_prediction.json          # ผลทำนายล่าสุด
├─ analyses/                       # รายงานวิเคราะห์ที่สร้างแล้ว
└─ tests/                          # ชุดทดสอบระบบ
```

## โฟลเดอร์ข้อมูลที่ระบบใช้

- `Match Logs/` ข้อมูลแมตช์ย้อนหลังรายนัด
- `sofaplayer/` สถิติผู้เล่นรายทีม
- `position/` ตำแหน่งผู้เล่น
- `player_characteristics/` จุดเด่น/จุดอ่อนผู้เล่น
- `sofascore_team_data/` สถิติรวมระดับทีม
- `all stats/` ตารางคะแนนและสถิติเชิงลึกจากลีก
- `game flow/` เมตริก flow ของแต่ละทีม

## ความต้องการระบบ

- Python `3.10+`
- แนะนำให้รันบน Windows PowerShell

ติดตั้งแพ็กเกจที่จำเป็น:

```bash
pip install pandas numpy scipy requests openpyxl
```

## การตั้งค่า Gemini API (ไม่บังคับ)

ถ้าต้องการให้สร้างรายงานข้อความ AI ในโฟลเดอร์ `analyses/`:

PowerShell:

```powershell
$env:GEMINI_API_KEY = "your_api_key_here"
```

CMD:

```cmd
set GEMINI_API_KEY=your_api_key_here
```

หรือใส่ key ลงไฟล์ `gemini_key.txt` (1 บรรทัด) ที่ root โปรเจกต์

หมายเหตุ: ถ้าไม่มีทั้ง `GEMINI_API_KEY` และ `gemini_key.txt` ระบบยังคำนวณ prediction และเขียน `latest_prediction.json` ได้ แต่จะไม่สร้างรายงาน AI

## วิธีใช้งานแบบเร็ว

1. ตรวจความพร้อมระบบ

```bash
python scripts/system_check.py
```

2. อัปเดตข้อมูลล่าสุด (แนะนำก่อนวิเคราะห์)

```bash
python scripts/run_update.py --preflight-only
python scripts/run_update.py
```

3. เตรียม context ก่อนแข่งใน `match_context.txt` (ถ้ามี)

ตัวอย่างขั้นต่ำ:

```text
Match: Arsenal vs Liverpool
Date: 2026-02-16
League: Premier League

**Confirmed Lineups:**
**Arsenal (4-3-3):**
* **GK:** ...
* **DEF:** ...
* **MID:** ...
* **FW:** ...

**Liverpool (4-3-3):**
* **GK:** ...
* **DEF:** ...
* **MID:** ...
* **FW:** ...
```

4. รันวิเคราะห์แมตช์

```bash
python analyze_match.py Arsenal Liverpool
```

5. บันทึก prediction ลง tracker

```bash
python update_tracker.py save
```

หรือใช้แบตช์ไฟล์

```bash
savepredic.bat
```

6. หลังแมตช์จบ: อัปเดตผล/สรุป

```bash
python update_tracker.py
python update_tracker.py update_bets
```

## คำสั่งที่ใช้บ่อย

```bash
# วิเคราะห์แมตช์
python analyze_match.py <HomeTeam> <AwayTeam>

# บันทึก latest_prediction.json ลง prediction_tracker.xlsx
python update_tracker.py save

# ลบข้อมูลซ้ำใน tracker
python update_tracker.py clean

# อัปเดตผล bet (อิง Actual_Score จาก Predictions)
python update_tracker.py update_bets

# สร้าง calibration จากผลจริงเพื่อปรับโมเดลรอบถัดไป
python update_tracker.py calibrate

# ประเมินคุณภาพโมเดล (Brier/LogLoss/MAE + quality gates)
python update_tracker.py evaluate

# ปิดลูปหลังแข่งอัตโนมัติ: update_bets -> calibrate -> evaluate
python update_tracker.py close_loop

# วิเคราะห์แบบย้อนกลับสกอร์เป้าหมาย
python analyze_match.py <HomeTeam> <AwayTeam> --target-score 0-2

# pipeline โหมดดูขั้นตอนอย่างเดียว
python scripts/run_update.py --dry-run

# pipeline โหมดไปต่อแม้บางสเต็ปล้ม
python scripts/run_update.py --continue-on-error
```

## Output ที่จะได้

- `latest_prediction.json`
  - ความน่าจะเป็น Home/Draw/Away
  - สกอร์ที่น่าจะเป็นมากที่สุด
  - `Bet_Data` และ `Bet_Detail`
  - `Tactical_Scenarios` (ฉากเกมเชิงแท็กติกพร้อมโอกาสเกิดและโอกาสนำไปสู่ประตู)
- `model_calibration.json`
  - ค่าปรับ global/league/team จากผลจริง
- `model_performance.json`
  - ตัวชี้วัดคุณภาพโมเดล + quality gates
- `analyses/analysis_<Home>_<Away>.md` (เมื่อ Gemini ตอบสำเร็จ)
- `prediction_tracker.xlsx`
  - แผ่นหลัก: `Predictions`, `bet data`, `bet predic`, `bet ev`, `Summary`
  - แผ่นประเมิน: `Model Eval`, `Model Eval League`, `Model Eval Segments`
- `backups/prediction_tracker_backup_*.xlsx` (สำรองอัตโนมัติก่อนเขียนไฟล์)

## การทดสอบ

```bash
python -m unittest tests/test_full_system.py tests/test_simulator_v9.py tests/test_automation_paths.py
```

## หมายเหตุสำคัญ

- ควรใช้ชื่อทีมให้ใกล้กับชื่อใน dataset มากที่สุด เพื่อลดปัญหา match ชื่อไม่เจอ
- ถ้า `GEMINI_API_KEY` ไม่ถูกตั้งค่า รายงาน AI จะไม่ถูกสร้าง แต่ prediction หลักยังทำงาน
- ถ้าไม่ใช้ env var สามารถใส่ key ใน `gemini_key.txt` ได้
- การรัน `python update_tracker.py` แบบไม่ใส่อาร์กิวเมนต์ จะอัปเดต `Summary` และแสดงคำแนะนำให้กรอก `Actual_Score/Actual_Result` ก่อนค่อยรัน `python update_tracker.py update_bets`
- pipeline scraping พึ่งพาโครงสร้างเว็บภายนอก ถ้า schema ต้นทางเปลี่ยน สคริปต์บางส่วนอาจต้องปรับ

## Disclaimer

โปรเจกต์นี้ใช้เพื่อการวิเคราะห์ข้อมูลและการพัฒนาโมเดล ผลลัพธ์เป็นความน่าจะเป็น ไม่ใช่การการันตีผลการแข่งขัน
