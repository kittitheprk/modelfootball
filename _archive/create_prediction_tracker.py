import pandas as pd
from datetime import datetime
import os

def create_prediction_tracker():
    """Create an Excel file to track predictions vs actual results"""
    
    # Define columns for the tracker
    columns = [
        'Date',                    # วันที่วิเคราะห์
        'Match',                   # คู่แข่งขัน (Home vs Away)
        'League',                  # ลีก
        'Home_Team',               # ทีมเหย้า
        'Away_Team',               # ทีมเยือน
        'Pred_Home_Win%',          # ทำนาย % ทีมเหย้าชนะ
        'Pred_Draw%',              # ทำนาย % เสมอ
        'Pred_Away_Win%',          # ทำนาย % ทีมเยือนชนะ
        'Pred_Score',              # สกอร์ที่ทำนาย (e.g., "1-2")
        'Pred_Result',             # ผลที่ทำนาย (Home/Draw/Away)
        'Actual_Score',            # สกอร์จริง (ใส่ทีหลัง)
        'Actual_Result',           # ผลจริง (Home/Draw/Away)
        'Result_Correct',          # ทำนายผลถูกไหม? (TRUE/FALSE)
        'Score_Correct',           # ทำนายสกอร์ถูกไหม? (TRUE/FALSE)
        'Goal_Diff_Error',         # ความผิดพลาดของ Goal Difference
        'Notes'                    # หมายเหตุ
    ]
    
    # Create DataFrame with existing predictions
    data = [
        {
            'Date': '2026-02-08',
            'Match': 'Milan vs Como',
            'League': 'Serie A',
            'Home_Team': 'Milan',
            'Away_Team': 'Como',
            'Pred_Home_Win%': 29.7,
            'Pred_Draw%': 27.3,
            'Pred_Away_Win%': 43.0,
            'Pred_Score': '0-1',
            'Pred_Result': 'Away',
            'Actual_Score': '',
            'Actual_Result': '',
            'Result_Correct': '',
            'Score_Correct': '',
            'Goal_Diff_Error': '',
            'Notes': 'Postponed match. Como 6th vs Milan 2nd. PPDA analysis favored Como.'
        },
        {
            'Date': '2026-02-08',
            'Match': 'Brighton vs Crystal Palace',
            'League': 'Premier League',
            'Home_Team': 'Brighton',
            'Away_Team': 'Crystal Palace',
            'Pred_Home_Win%': 33.3,
            'Pred_Draw%': 32.7,
            'Pred_Away_Win%': 34.0,
            'Pred_Score': '1-1',
            'Pred_Result': 'Draw',
            'Actual_Score': '',
            'Actual_Result': '',
            'Result_Correct': '',
            'Score_Correct': '',
            'Goal_Diff_Error': '',
            'Notes': 'M23 Derby. Both teams in bad form. Lacroix (7.7) MOTM in live analysis.'
        },
        {
            'Date': '2026-02-08',
            'Match': 'Liverpool vs Manchester City',
            'League': 'Premier League',
            'Home_Team': 'Liverpool',
            'Away_Team': 'Manchester City',
            'Pred_Home_Win%': 11.0,
            'Pred_Draw%': 22.7,
            'Pred_Away_Win%': 66.3,
            'Pred_Score': '1-2',
            'Pred_Result': 'Away',
            'Actual_Score': '',
            'Actual_Result': '',
            'Result_Correct': '',
            'Score_Correct': '',
            'Goal_Diff_Error': '',
            'Notes': 'Szoboszlai at RB = risk. Haaland main threat. Simulation: 0-2.'
        }
    ]
    
    df = pd.DataFrame(data, columns=columns)
    
    # Save to Excel
    filename = 'prediction_tracker.xlsx'
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Predictions', index=False)
        
        # Create a summary sheet
        summary_df = pd.DataFrame({
            'Metric': [
                'Total Predictions',
                'Results Verified',
                'Result Accuracy (%)',
                'Exact Score Accuracy (%)',
                'Avg Goal Diff Error',
                'Home Win Predictions',
                'Draw Predictions',
                'Away Win Predictions'
            ],
            'Value': [
                len(df),
                0,  # Will be updated as results come in
                '=IF(B3>0, COUNTIF(Predictions!L:L,"TRUE")/B3*100, "N/A")',
                '=IF(B3>0, COUNTIF(Predictions!M:M,"TRUE")/B3*100, "N/A")',
                '=IF(B3>0, AVERAGE(Predictions!N:N), "N/A")',
                len(df[df['Pred_Result'] == 'Home']),
                len(df[df['Pred_Result'] == 'Draw']),
                len(df[df['Pred_Result'] == 'Away'])
            ]
        })
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    print(f"[OK] Created prediction tracker: {filename}")
    print(f"[INFO] Contains {len(df)} predictions ready for verification")
    print("\nInstructions:")
    print("1. After each match ends, fill in 'Actual_Score' and 'Actual_Result'")
    print("2. Set 'Result_Correct' to TRUE/FALSE")
    print("3. Set 'Score_Correct' to TRUE/FALSE")
    print("4. Calculate 'Goal_Diff_Error' = |Predicted GD - Actual GD|")
    print("5. Summary sheet will show overall accuracy")

if __name__ == "__main__":
    create_prediction_tracker()
