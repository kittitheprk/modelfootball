
import pandas as pd
import os

file_path = 'sofascore_team_data/Bundesliga_Team_Stats.xlsx'
if os.path.exists(file_path):
    try:
        df = pd.read_excel(file_path)
        print("Columns:", list(df.columns))
        print("First row:", df.head(1).to_string())
    except Exception as e:
        print(e)
else:
    print(f"File not found: {file_path}")
