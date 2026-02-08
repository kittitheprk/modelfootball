import pandas as pd
path = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\all stats\Premier_League_Stats.xlsx"
df = pd.read_excel(path, sheet_name='Defensive Actions')
print(list(df.columns))
