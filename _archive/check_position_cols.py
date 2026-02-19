
import pandas as pd
import os
import sys

# Set stdout encoding to utf-8 to handle Thai characters if possible, though mostly we just avoid printing the path if it fails
sys.stdout.reconfigure(encoding='utf-8')

def check_columns(file_path, sheet_name=None):
    try:
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=5)
        else:
            df = pd.read_excel(file_path, nrows=5)
        
        # Safe printing of filename
        filename = os.path.basename(file_path)
        print(f"\n--- Columns in {filename} [{sheet_name or 'Default'}] ---")
        print(list(df.columns))
    except Exception as e:
        print(f"Error reading file (check path/encoding): {e}")

# Check SofaScore data
sofascore_path = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\sofascore_team_data\Premier_League_Team_Stats.xlsx"
try:
    xl = pd.ExcelFile(sofascore_path)
    print(f"\nSofaScore Sheets: {xl.sheet_names[:5]}")
    check_columns(sofascore_path, sheet_name=xl.sheet_names[0])
except Exception as e:
    print(f"Error accessing SofaScore file: {e}")

# Check 'all stats' (likely FBref or WhoScored aggregated)
all_stats_path = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\all stats\Premier_League_Stats.xlsx"
try:
    xl = pd.ExcelFile(all_stats_path)
    print(f"\nAll Stats Sheets: {xl.sheet_names[:5]}")
    check_columns(all_stats_path, sheet_name=xl.sheet_names[0])
except Exception as e:
    print(f"Error accessing All Stats file: {e}")

# Check Player Characteristics
chars_path = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\player_characteristics\Premier_League_Characteristics.xlsx"
try:
    xl = pd.ExcelFile(chars_path)
    print(f"\nCharacteristics Sheets: {xl.sheet_names[:5]}")
    check_columns(chars_path, sheet_name=xl.sheet_names[0])
except Exception as e:
    print(f"Error accessing Characteristics file: {e}")
