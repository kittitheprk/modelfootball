import pandas as pd
import os

all_stats_path = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\all stats\Premier_League_Stats.xlsx"

def inspect_standard_cols():
    try:
        df = pd.read_excel(all_stats_path, sheet_name='Standard Stats')
        print("Standard Stats Columns:", list(df.columns))
        
        df_shooting = pd.read_excel(all_stats_path, sheet_name='Shooting')
        print("Shooting Columns:", list(df_shooting.columns[:20]))

        df_def = pd.read_excel(all_stats_path, sheet_name='Defensive Actions')
        print("Defense Columns:", list(df_def.columns[:20]))

    except Exception as e:
        print(e)

inspect_standard_cols()
