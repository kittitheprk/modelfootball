import pandas as pd
path = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\all stats\Premier_League_Stats.xlsx"

def check_cols():
    try:
        xls = pd.ExcelFile(path)
        
        # Check Standard Stats for Goals - PK
        if 'Standard Stats' in xls.sheet_names:
            df = pd.read_excel(xls, 'Standard Stats')
            print("Standard Stats:", list(df.columns)[:40])
            
        # Check Passing for Cmp%
        if 'Passing' in xls.sheet_names:
            df = pd.read_excel(xls, 'Passing')
            print("\nPassing:", list(df.columns))

        # Check Possession for Touches Att Pen, PrgR
        if 'Possession' in xls.sheet_names:
            df = pd.read_excel(xls, 'Possession')
            print("\nPossession:", list(df.columns))
            
    except Exception as e:
        print(e)

check_cols()
