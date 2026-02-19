# สรุประบบวิเคราะห์ล่าสุด (System Summary)

จากการตรวจสอบ codebase ล่าสุด พบว่าระบบประกอบด้วย 2 ส่วนหลัก คือ **Production System (v9)** และ **Experimental System (Demo v2)** ครับ

## 1. Production System: Simulator v9 (`simulator_v9.py`)
นี่คือระบบหลักที่ใช้ในปัจจุบัน (อ้างอิงจาก `README.md` และไฟล์ `analyze_match.py`)

### ความสามารถใหม่ (Key Features)
*   **Player Roles & Ratings**:
    *   แยกระบบคะแนนผู้เล่นละเอียดขึ้น: `Attack`, `Defense`, `Control`.
    *   คำนวณ Rating ตามตำแหน่ง (GK, DEF, MID, ATT) โดยมีการถ่วงน้ำหนักสถิติที่ต่างกัน
    *   **Specific Traits**: มีการปรับคะแนนตามจุดแข็ง/จุดอ่อน (Strengths/Weaknesses) เช่น "finishing", "tackling".
*   **Advanced Metrics**:
    *   **xT Proxy (Expected Threat)**: คำนวณความอันตรายในการสร้างสรรค์เกมจาก `xa_p90`, `key_passes`, `dribbles` โดยไม่ต้องใช้ Event Data ราคาแพง
    *   **Workload/Fatigue**: คำนวณความล้าจาก `minutesPlayed` และจำนวนนัดที่ลงสนาม
*   **Dynamic Lineups**:
    *   รองรับ **Confirmed Lineups** จาก SofaScore widget
    *   ระบบ Hybrid: ถ้าไม่มี lineup ตัวจริง จะใช้ Projected Lineup จากสถิติความสม่ำเสมอ (`__priority`)
    *   คำนวณ `attack_delta` / `defense_delta` เพื่อปรับค่าพลังทีมตามผู้เล่นที่ลงจริง

### การใช้งาน (Workflow)
คำสั่งหลักยังคงเป็น:
```bash
python analyze_match.py "Home Team" "Away Team"
```

## 2. Experimental System: Demo Model v2 (`demo_model_v2/`)
เป็นSandbox สำหรับทดสอบฟีเจอร์ใหม่ที่กำลังพัฒนา

### ฟีเจอร์ทดลอง (Experimental Features)
*   **Player Impact Engine (`player_impact_engine.py`)**:
    *   ระบบคำนวณ **"Missing Player Tax"**: หักลบความเก่งของทีมเมื่อขาดตัวหลัก
    *   Logic: เทียบ Rating ของตัวจริงที่หายไป vs ตัวสำรอง -> แปลงเป็น % ประสิทธิภาพที่ลดลง (Attack/Defense Tax)
    *   รองรับการระบุชื่อตัวเจ็บผ่าน command line argument
*   **Simplified Runner (`run_demo.py`)**:
    *   สคริปต์แยกสำหรับรันโมเดลทดลองโดยอิสระ
    *   แสดงผล **Score Probability Heatmap** และ **Simulation Results** แบบรวดเร็ว

### การใช้งาน (Demo)
```bash
cd demo_model_v2
python run_demo.py "Home Team" "Away Team" --missing_home "Saka, Rice"
```

---

## สรุปสถานะปัจจุบัน
*   **ใช้งานจริง (Daily Analysis)**: ให้ใช้ `analyze_match.py` (v9) เพราะมีความเสถียรและฟีเจอร์ครบ (Context, Tracker, Visualization)
*   **พัฒนาต่อ (R&D)**: ใช้ `demo_model_v2` เพื่อทดสอบ Logic ใหม่ๆ (เช่น Impact Tax) ก่อนนำไปรวมใน v9 หรือ v10 ต่อไป
