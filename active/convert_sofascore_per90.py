import argparse
from pathlib import Path

import pandas as pd


STATS_TO_CONVERT = [
    "goalsScored",
    "goalsConceded",
    "shots",
    "shotsOnTarget",
    "blockedShots",
    "corners",
    "fouls",
    "yellowCards",
    "redCards",
    "bigChances",
    "bigChancesMissed",
    "hitWoodwork",
    "counterAttacks",
    "penaltyGoals",
    "accuratePasses",
    "keyPasses",
    "longBalls",
    "crosses",
    "tackles",
    "interceptions",
    "clearances",
    "saves",
    "ballsRecovered",
    "duelsWon",
    "groundDuelsWon",
    "aerialDuelsWon",
    "possessionLost",
    "successfulDribbles",
]


def build_per90(df):
    out = df.copy()
    if "Matches_Played" not in out.columns:
        return out

    matches = pd.to_numeric(out["Matches_Played"], errors="coerce")
    valid = matches > 0
    safe_matches = matches.where(valid)

    for key in STATS_TO_CONVERT:
        if key not in out.columns:
            continue
        values = pd.to_numeric(out[key], errors="coerce")
        out[f"{key}_per_90"] = (values / safe_matches).round(2)

    return out


def convert_file(src_file, dst_file):
    df = pd.read_excel(src_file)
    converted = build_per90(df)
    dst_file.parent.mkdir(parents=True, exist_ok=True)
    converted.to_excel(dst_file, index=False)
    return len(converted)


def run(input_dir, output_dir):
    src = Path(input_dir)
    dst = Path(output_dir)
    files = sorted(src.glob("*_Team_Stats.xlsx"))

    if not files:
        print(f"No files found in {src}")
        return 0

    print(f"Converting {len(files)} files from {src} -> {dst}")
    for file_path in files:
        target = dst / file_path.name
        rows = convert_file(file_path, target)
        print(f"  + {file_path.name} ({rows} rows)")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create derived SofaScore *_per_90 files from raw team stats."
    )
    parser.add_argument(
        "--input-dir",
        default="sofascore_team_data",
        help="Directory containing raw *_Team_Stats.xlsx files.",
    )
    parser.add_argument(
        "--output-dir",
        default="active/sofascore_team_data",
        help="Directory to write derived per90 files.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(run(args.input_dir, args.output_dir))
