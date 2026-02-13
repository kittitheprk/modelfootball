import pandas as pd

file_all_stats = r"c:/Users/errig/OneDrive - มหาวิทยาลัยสยาม (1)/Desktop/model football/all stats/Premier_League_Stats.xlsx"
file_match_logs = r"c:/Users/errig/OneDrive - มหาวิทยาลัยสยาม (1)/Desktop/model football/Match Logs/Premier_League/Arsenal.xlsx"

print("--- All Stats: Team_Stats ---")
try:
    df = pd.read_excel(file_all_stats, sheet_name='Team_Stats', nrows=0)
    print(list(df.columns))
except Exception as e:
    print(e)

print("\n--- All Stats: Defensive Actions ---")
try:
    df = pd.read_excel(file_all_stats, sheet_name='Defensive Actions', nrows=0)
    print(list(df.columns))
except Exception as e:
    print(e)
    
print("\n--- All Stats: Miscellaneous Stats ---")
try:
    df = pd.read_excel(file_all_stats, sheet_name='Miscellaneous Stats', nrows=0)
    print(list(df.columns))
except Exception as e:
    print(e)

print("\n--- Match Logs: Defensive Actions ---")
try:
    df = pd.read_excel(file_match_logs, sheet_name='Defensive Actions', nrows=0)
    print(list(df.columns))
except Exception as e:
    print(e)

print("\n--- Match Logs: Miscellaneous Stats ---")
try:
    df = pd.read_excel(file_match_logs, sheet_name='Miscellaneous Stats', nrows=0)
    print(list(df.columns))
except Exception as e:
    print(e)
