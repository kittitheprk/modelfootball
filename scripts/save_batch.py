
import json
import os
import pandas as pd
import subprocess
import time

matches = [
    {
        "Date": "2026-02-10", # Approximate date, using tomorrow's date as per context
        "Match": "Valencia vs Real Madrid",
        "League": "La_Liga",
        "Home_Team": "Valencia",
        "Away_Team": "Real_Madrid",
        "Pred_Home_Win": 15.0, # Estimated from context
        "Pred_Draw": 20.0,
        "Pred_Away_Win": 65.0,
        "Pred_Score": "0-2",
        "Pred_Result": "Away"
    },
    {
        "Date": "2026-02-10",
        "Match": "Juventus vs Lazio",
        "League": "Serie_A",
        "Home_Team": "Juventus",
        "Away_Team": "Lazio",
        "Pred_Home_Win": 45.0, # Estimated
        "Pred_Draw": 35.0,
        "Pred_Away_Win": 20.0,
        "Pred_Score": "1-0",
        "Pred_Result": "Home"
    },
    {
        "Date": "2026-02-10",
        "Match": "PSG vs Marseille",
        "League": "Ligue_1",
        "Home_Team": "PSG",
        "Away_Team": "Marseille",
        "Pred_Home_Win": 40.0, # Estimated "Close simulation"
        "Pred_Draw": 35.0,
        "Pred_Away_Win": 25.0,
        "Pred_Score": "1-1",
        "Pred_Result": "Draw"
    }
]

for match in matches:
    print(f"Processing {match['Match']}...")
    with open("latest_prediction.json", "w", encoding='utf-8') as f:
        json.dump(match, f, indent=4, ensure_ascii=False)
    
    # Run the update_tracker.py save command
    # using current python executable
    subprocess.run(["python", "update_tracker.py", "save"], check=True)
    time.sleep(1) # Small pause
    
print("\nBatch save completed.")
