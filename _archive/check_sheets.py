import pandas as pd
path = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\all stats\Premier_League_Stats.xlsx"
print(pd.ExcelFile(path).sheet_names)
