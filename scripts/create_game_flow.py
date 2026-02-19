import glob
import os
from pathlib import Path

import pandas as pd


# Derived metrics:
# 1) calc_PPDA = accurateOwnHalfPassesAgainst / (tackles + interceptions + fouls)
# 2) calc_OPPDA = accurateOwnHalfPasses / (tacklesAgainst + interceptionsAgainst)
# 3) calc_FieldTilt_Pct = accurateOppositionHalfPasses / (accurateOppositionHalfPasses + accurateOppositionHalfPassesAgainst)
# 4) calc_HighError_Rate = errorsLeadingToShot + errorsLeadingToGoal
# 5) calc_Directness = totalLongBalls / totalPasses
# 6) calc_BigChance_Diff = bigChances - bigChancesAgainst

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = BASE_DIR / "sofascore_team_data"
DEST_DIR = BASE_DIR / "game flow"


def calculate_metrics(df):
    df = df.copy()

    defensive_actions = df["tackles"] + df["interceptions"] + df["fouls"]
    df["calc_PPDA"] = df["accurateOwnHalfPassesAgainst"] / defensive_actions.replace(0, pd.NA)

    defensive_actions_against = df["tacklesAgainst"] + df["interceptionsAgainst"]
    df["calc_OPPDA"] = df["accurateOwnHalfPasses"] / defensive_actions_against.replace(0, pd.NA)

    total_opp_half_passes = df["accurateOppositionHalfPasses"] + df["accurateOppositionHalfPassesAgainst"]
    df["calc_FieldTilt_Pct"] = df["accurateOppositionHalfPasses"] / total_opp_half_passes.replace(0, pd.NA)

    df["calc_HighError_Rate"] = df["errorsLeadingToShot"] + df["errorsLeadingToGoal"]
    df["calc_Directness"] = df["totalLongBalls"] / df["totalPasses"].replace(0, pd.NA)
    df["calc_BigChance_Diff"] = df["bigChances"] - df["bigChancesAgainst"]
    return df


def main():
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    files = glob.glob(os.path.join(str(SOURCE_DIR), "*_Team_Stats.xlsx"))
    print(f"Found {len(files)} files.")

    for file_path in files:
        filename = os.path.basename(file_path)
        league_name = filename.replace("_Team_Stats.xlsx", "")
        print(f"Processing League: {league_name}")

        try:
            df = pd.read_excel(file_path)
            required_cols = [
                "Team_Name",
                "accurateOwnHalfPassesAgainst",
                "tackles",
                "interceptions",
                "fouls",
                "accurateOwnHalfPasses",
                "tacklesAgainst",
                "interceptionsAgainst",
                "accurateOppositionHalfPasses",
                "accurateOppositionHalfPassesAgainst",
                "errorsLeadingToShot",
                "errorsLeadingToGoal",
                "totalLongBalls",
                "totalPasses",
                "bigChances",
                "bigChancesAgainst",
            ]

            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                print(f"  SKIPPING {filename}: Missing columns: {missing}")
                continue

            df_calculated = calculate_metrics(df)
            output_cols = [
                "Team_Name",
                "calc_PPDA",
                "calc_OPPDA",
                "calc_FieldTilt_Pct",
                "calc_HighError_Rate",
                "calc_Directness",
                "calc_BigChance_Diff",
            ]
            final_df = df_calculated[output_cols]

            save_path = DEST_DIR / f"{league_name}_GameFlow.xlsx"
            final_df.to_excel(save_path, index=False)
            print(f"  Saved consolidated file for {league_name}")
        except Exception as exc:
            print(f"  Error processing {filename}: {exc}")


if __name__ == "__main__":
    main()
