import pandas as pd
import os

filename = 'prediction_tracker.xlsx'

# ============================================================
# RECOVERY v2: Rebuild from USER's original data + update_tracker.py
# ============================================================

predictions = [
    # === From user's original data (verbatim) ===
    {"Date": "2026-02-08", "Match": "Brighton vs Crystal Palace", "League": "Premier League",
     "Home_Team": "Brighton", "Away_Team": "Crystal Palace",
     "Pred_Home_Win%": 33.3, "Pred_Draw%": 32.7, "Pred_Away_Win%": 34.0,
     "Pred_Score": "1-1", "Pred_Result": "Draw",
     "Actual_Score": "0-1", "Actual_Result": "Away",
     "Result_Correct": False, "Score_Correct": False, "Goal_Diff_Error": 1,
     "Notes": "MOTM: Lacroix (8.0). Sarr scored 61'. xG: Brighton 0.85 vs Palace 1.16."},

    {"Date": "2026-02-08", "Match": "Liverpool vs Manchester City", "League": "Premier League",
     "Home_Team": "Liverpool", "Away_Team": "Manchester City",
     "Pred_Home_Win%": 11.0, "Pred_Draw%": 22.7, "Pred_Away_Win%": 66.3,
     "Pred_Score": "1-2", "Pred_Result": "Away",
     "Actual_Score": "1-2", "Actual_Result": "Away",
     "Result_Correct": True, "Score_Correct": True, "Goal_Diff_Error": 0,
     "Notes": "MOTM: Bernardo Silva. Goals: Szoboszlai 74', B.Silva 84', Haaland 90+3' (pen). xG: 1.21-2.91. Szoboszlai red card 90+13'."},

    {"Date": "2026-02-09", "Match": "Roma vs Cagliari", "League": "Serie_A",
     "Home_Team": "Roma", "Away_Team": "Cagliari",
     "Pred_Home_Win%": 78.0, "Pred_Draw%": 19.33, "Pred_Away_Win%": 2.67,
     "Pred_Score": "1-0", "Pred_Result": "Home",
     "Actual_Score": "2-0", "Actual_Result": "Home",
     "Result_Correct": True, "Score_Correct": False, "Goal_Diff_Error": 1,
     "Notes": "MOTM: Donyell Malen (8.2). 2 goals."},

    {"Date": "2026-02-10", "Match": "Valencia vs Real Madrid", "League": "La_Liga",
     "Home_Team": "Valencia", "Away_Team": "Real Madrid",
     "Pred_Home_Win%": 15.0, "Pred_Draw%": 20.0, "Pred_Away_Win%": 65.0,
     "Pred_Score": "0-2", "Pred_Result": "Away",
     "Actual_Score": "0-2", "Actual_Result": "Away",
     "Result_Correct": True, "Score_Correct": True, "Goal_Diff_Error": 0,
     "Notes": "MOTM: Alvaro Carreras (7.9). Scorer: Carreras 65', Mbappe 90+1'."},

    {"Date": "2026-02-10", "Match": "Juventus vs Lazio", "League": "Serie_A",
     "Home_Team": "Juventus", "Away_Team": "Lazio",
     "Pred_Home_Win%": 45.0, "Pred_Draw%": 35.0, "Pred_Away_Win%": 20.0,
     "Pred_Score": "1-0", "Pred_Result": "Home",
     "Actual_Score": "2-2", "Actual_Result": "Draw",
     "Result_Correct": False, "Score_Correct": False, "Goal_Diff_Error": 1,
     "Notes": "MOTM: Pierre Kalulu (8.2). Late equalizer Kalulu 90+6'. Juve recovered from 0-2."},

    {"Date": "2026-02-10", "Match": "PSG vs Marseille", "League": "Ligue_1",
     "Home_Team": "PSG", "Away_Team": "Marseille",
     "Pred_Home_Win%": 40.0, "Pred_Draw%": 35.0, "Pred_Away_Win%": 25.0,
     "Pred_Score": "1-1", "Pred_Result": "Draw",
     "Actual_Score": "5-0", "Actual_Result": "Home",
     "Result_Correct": False, "Score_Correct": False, "Goal_Diff_Error": 5,
     "Notes": "MOTM: Ousmane Dembele (10.0). 2 Goals. Total domination."},

    {"Date": "2026-02-10", "Match": "Chelsea vs Leeds United", "League": "Premier_League",
     "Home_Team": "Chelsea", "Away_Team": "Leeds United",
     "Pred_Home_Win%": 68.0, "Pred_Draw%": 14.33, "Pred_Away_Win%": 17.67,
     "Pred_Score": "2-1", "Pred_Result": "Home",
     "Actual_Score": "2-2", "Actual_Result": "Draw",
     "Result_Correct": False, "Score_Correct": False, "Goal_Diff_Error": 1,
     "Notes": "Lead 2-0 -> Draw 2-2. Nmecha & Okafor scored for Leeds."},

    {"Date": "2026-02-10", "Match": "Tottenham vs Newcastle", "League": "Premier_League",
     "Home_Team": "Tottenham", "Away_Team": "Newcastle",
     "Pred_Home_Win%": 17.67, "Pred_Draw%": 13.0, "Pred_Away_Win%": 69.33,
     "Pred_Score": "1-2", "Pred_Result": "Away",
     "Actual_Score": "1-2", "Actual_Result": "Away",
     "Result_Correct": True, "Score_Correct": True, "Goal_Diff_Error": 0,
     "Notes": "Perfect Prediction! Thiaw & Ramsey scored."},

    {"Date": "2026-02-10", "Match": "West Ham United vs Manchester United", "League": "Premier_League",
     "Home_Team": "West Ham United", "Away_Team": "Manchester United",
     "Pred_Home_Win%": 0.33, "Pred_Draw%": 1.33, "Pred_Away_Win%": 98.33,
     "Pred_Score": "0-3", "Pred_Result": "Away",
     "Actual_Score": "1-1", "Actual_Result": "Draw",
     "Result_Correct": False, "Score_Correct": False, "Goal_Diff_Error": 3,
     "Notes": "Man Utd late equalizer (Sesko)."},

    {"Date": "2026-02-10", "Match": "Everton vs Bournemouth", "League": "Premier_League",
     "Home_Team": "Everton", "Away_Team": "Bournemouth",
     "Pred_Home_Win%": 7.67, "Pred_Draw%": 17.33, "Pred_Away_Win%": 75.0,
     "Pred_Score": "0-2", "Pred_Result": "Away",
     "Actual_Score": "1-2", "Actual_Result": "Away",
     "Result_Correct": True, "Score_Correct": False, "Goal_Diff_Error": 1,
     "Notes": "Everton red card (O'Brien). Comeback win for BOU."},

    {"Date": "2026-02-12", "Match": "Sunderland vs Liverpool", "League": "Premier_League",
     "Home_Team": "Sunderland", "Away_Team": "Liverpool",
     "Pred_Home_Win%": 28.8, "Pred_Draw%": 27.84, "Pred_Away_Win%": 43.36,
     "Pred_Score": "0-1", "Pred_Result": "Away",
     "Actual_Score": "0-1", "Actual_Result": "Away",
     "Result_Correct": True, "Score_Correct": True, "Goal_Diff_Error": 0,
     "Notes": "Simulator v5.0 (Moneyball) Exact Score! Van Dijk scored."},

    # === From update_tracker.py (these were added after the user's data) ===
    {"Date": "2026-02-11", "Match": "Rennes vs Paris S-G", "League": "Ligue_1",
     "Home_Team": "Rennes", "Away_Team": "Paris S-G",
     "Pred_Home_Win%": 25.0, "Pred_Draw%": 29.0, "Pred_Away_Win%": 46.0,
     "Pred_Score": "1-2", "Pred_Result": "Away",
     "Actual_Score": "0-3", "Actual_Result": "Away",
     "Result_Correct": True, "Score_Correct": False, "Goal_Diff_Error": 2,
     "Notes": "Sim v6.0 Correct result. Barcola hat-trick."},

    {"Date": "2026-02-12", "Match": "Atletico Madrid vs Barcelona", "League": "La_Liga",
     "Home_Team": "Atletico Madrid", "Away_Team": "Barcelona",
     "Pred_Home_Win%": 25.0, "Pred_Draw%": 29.1, "Pred_Away_Win%": 45.9,
     "Pred_Score": "1-1", "Pred_Result": "Away",
     "Actual_Score": "4-0", "Actual_Result": "Home",
     "Result_Correct": False, "Score_Correct": False, "Goal_Diff_Error": 4,
     "Notes": "System failure. Predicted Away/Draw, Actual Home rout."},

    {"Date": "2026-02-12", "Match": "Brentford vs Arsenal", "League": "Premier_League",
     "Home_Team": "Brentford", "Away_Team": "Arsenal",
     "Pred_Home_Win%": 20.0, "Pred_Draw%": 28.0, "Pred_Away_Win%": 52.0,
     "Pred_Score": "0-2", "Pred_Result": "Away",
     "Actual_Score": "1-1", "Actual_Result": "Draw",
     "Result_Correct": False, "Score_Correct": False, "Goal_Diff_Error": 2,
     "Notes": "Arsenal dropped points. Late equalizer by Brentford."},

    {"Date": "2026-02-13", "Match": "Dortmund vs Mainz", "League": "Bundesliga",
     "Home_Team": "Dortmund", "Away_Team": "Mainz",
     "Pred_Home_Win%": 65.5, "Pred_Draw%": 17.0, "Pred_Away_Win%": 17.5,
     "Pred_Score": "3-1", "Pred_Result": "Home",
     "Actual_Score": "4-0", "Actual_Result": "Home",
     "Result_Correct": True, "Score_Correct": False, "Goal_Diff_Error": 2,
     "Notes": "Guirassy scored 2 goals. Comfortable win as predicted."},

    {"Date": "2026-02-13", "Match": "Pisa vs Milan", "League": "Serie_A",
     "Home_Team": "Pisa", "Away_Team": "Milan",
     "Pred_Home_Win%": 22.0, "Pred_Draw%": 23.6, "Pred_Away_Win%": 54.4,
     "Pred_Score": "0-1", "Pred_Result": "Away",
     "Actual_Score": "1-2", "Actual_Result": "Away",
     "Result_Correct": True, "Score_Correct": False, "Goal_Diff_Error": 0,
     "Notes": "Correct Result & Goal Diff. Milan won 2-1 (Modric winner)."},

    {"Date": "2026-02-14", "Match": "Leverkusen vs St. Pauli", "League": "Bundesliga",
     "Home_Team": "Leverkusen", "Away_Team": "St. Pauli",
     "Pred_Home_Win%": 60.2, "Pred_Draw%": 19.73, "Pred_Away_Win%": 20.07,
     "Pred_Score": "2-1", "Pred_Result": "Home",
     "Actual_Score": "4-0", "Actual_Result": "Home",
     "Result_Correct": True, "Score_Correct": False, "Goal_Diff_Error": 3,
     "Notes": "Correct Result. Leverkusen dominant win (4-0)."},

    {"Date": "2026-02-15", "Match": "Inter vs Juventus", "League": "Serie_A",
     "Home_Team": "Inter", "Away_Team": "Juventus",
     "Pred_Home_Win%": 45.19, "Pred_Draw%": 24.5, "Pred_Away_Win%": 30.31,
     "Pred_Score": "1-1", "Pred_Result": "Home",
     "Actual_Score": "3-2", "Actual_Result": "Home",
     "Result_Correct": True, "Score_Correct": False, "Goal_Diff_Error": 1,
     "Notes": "Correct Result. High scoring derby (3-2). Zielinski winner."},
]

# Build DataFrame
df = pd.DataFrame(predictions)

# Column order (clean - no HDP/OU/BTTS columns)
column_order = [
    'Date', 'Match', 'League', 'Home_Team', 'Away_Team',
    'Pred_Home_Win%', 'Pred_Draw%', 'Pred_Away_Win%',
    'Pred_Score', 'Pred_Result',
    'Actual_Score', 'Actual_Result',
    'Result_Correct', 'Score_Correct', 'Goal_Diff_Error', 'Notes'
]
df = df[column_order]

# Calculate summary
verified = df[df['Actual_Result'].notna() & (df['Actual_Result'] != '')].copy()
total_verified = len(verified)
result_correct = verified['Result_Correct'].sum()
score_correct = verified['Score_Correct'].sum()
result_accuracy = (result_correct / total_verified) * 100 if total_verified > 0 else 0
score_accuracy = (score_correct / total_verified) * 100 if total_verified > 0 else 0
avg_gd_error = verified['Goal_Diff_Error'].mean() if total_verified > 0 else 0

summary_data = {
    'Metric': [
        'Total Predictions', 'Results Verified', 'Result Accuracy (%)',
        'Exact Score Accuracy (%)', 'Avg Goal Diff Error',
        'Home Win Predictions', 'Draw Predictions', 'Away Win Predictions',
        'Correct Predictions', 'Incorrect Predictions'
    ],
    'Value': [
        len(df), total_verified, f"{result_accuracy:.1f}%",
        f"{score_accuracy:.1f}%", f"{avg_gd_error:.2f}",
        len(df[df['Pred_Result'] == 'Home']),
        len(df[df['Pred_Result'] == 'Draw']),
        len(df[df['Pred_Result'] == 'Away']),
        int(result_correct), int(total_verified - result_correct)
    ]
}
summary_df = pd.DataFrame(summary_data)

# Save
with pd.ExcelWriter(filename, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='Predictions', index=False)
    summary_df.to_excel(writer, sheet_name='Summary', index=False)

print("=" * 60)
print("PREDICTION TRACKER RECOVERED v2!")
print("=" * 60)
print(f"Total Predictions: {len(df)}")
print(f"Verified Matches: {total_verified}/{len(df)}")
print(f"Result Accuracy: {result_accuracy:.1f}%")
print(f"Exact Score Accuracy: {score_accuracy:.1f}%")
print(f"Avg Goal Diff Error: {avg_gd_error:.2f}")
print("-" * 60)
print("Changes from v1:")
print("  - Removed: Brighton vs Liverpool (never predicted)")
print("  - Removed: Milan vs Como (not in original data)")
print("  - Added: Brighton vs Crystal Palace (correct match)")
print("  - Added: Liverpool vs Manchester City (missing)")
print("  - Fixed: All dates & percentages from user's original data")
print("  - Removed: Roma vs Cagliari duplicate (kept 2026-02-09)")
