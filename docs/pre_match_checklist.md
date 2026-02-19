# Pre-Match Checklist (30 Seconds)

ใช้รายการนี้ทุกครั้งก่อนรันวิเคราะห์คู่ใหม่ เพื่อลดโอกาสได้ผลทำนายจาก context เก่า

1. อัปเดต `match_context.txt` ให้ตรงคู่ใหม่
- ต้องมี `Match`, `Date`, `League` ตรงกับคู่ที่จะวิเคราะห์
- ถ้าใช้ iframe lineups ให้เป็น `id` ของคู่นั้นจริง

2. เช็ก preflight ของ pipeline
- รัน: `python update_football_data.py --headless --preflight-only`
- ผลที่ต้องได้: `Preflight OK`

3. รันวิเคราะห์คู่ใหม่
- รัน: `python analyze_match.py <Home> <Away>`

4. ตรวจคุณภาพผลลัพธ์ทันที
- เปิด `latest_prediction.json`
- เช็ก `QC_Flags` ต้องไม่มีข้อความ mismatch คู่แข่ง/context
- เช็ก `Match`, `Date`, `League` ต้องตรงคู่ที่เพิ่งรัน

5. บันทึกเข้าตารางติดตามผล
- รัน: `python update_tracker.py save`

## Quick Command Set

```bash
python update_football_data.py --headless --preflight-only
python analyze_match.py <Home> <Away>
python update_tracker.py save
```
