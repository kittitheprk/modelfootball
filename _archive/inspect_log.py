import pandas as pd
import os

try:
    path = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\sofaplayer\Premier_League\Arsenal_stats.xlsx"
    df = pd.read_excel(path)
    print("First 2 rows of Arsenal_stats.xlsx:")
    print(df.iloc[:2])
except Exception as e:
    print(f"Error: {e}")
