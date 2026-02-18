import argparse
from pathlib import Path

import pandas as pd


LEAGUES = [
    "Premier_League",
    "Serie_A",
    "La_Liga",
    "Ligue_1",
    "Bundesliga",
]

SOFASCORE_REQUIRED_COLUMNS = [
    "Team_Name",
    "Team_ID",
    "League",
    "Matches_Played",
    "goalsScored",
    "goalsConceded",
    "accurateOppositionHalfPasses",
    "successfulDribbles",
    "bigChancesCreated",
    "shotsFromInsideTheBox",
    "fastBreaks",
    "corners",
    "shotsOnTarget",
    "accurateLongBalls",
    "accurateOwnHalfPassesAgainst",
    "tackles",
    "interceptions",
    "fouls",
    "accurateOwnHalfPasses",
    "tacklesAgainst",
    "interceptionsAgainst",
    "accurateOppositionHalfPassesAgainst",
    "errorsLeadingToShot",
    "errorsLeadingToGoal",
    "totalLongBalls",
    "totalPasses",
    "bigChances",
    "bigChancesAgainst",
]

FBREF_REQUIRED_SHEETS = ["Team_Stats", "Player_Stats"]
FBREF_REQUIRED_COLUMNS = {
    "Team_Stats": ["Squad"],
    "Player_Stats": ["Player", "Squad"],
}
FBREF_DETAILED_SHEETS = [
    "Advanced Goalkeeping",
    "Shooting",
    "Passing",
    "Pass Types",
    "Goal and Shot Creation",
    "Defensive Actions",
    "Possession",
    "Playing Time",
    "Miscellaneous Stats",
]


def _missing_columns(df, required):
    return [c for c in required if c not in df.columns]


def validate_sofascore(base_dir):
    issues = []
    warnings = []

    for league in LEAGUES:
        file_path = base_dir / f"{league}_Team_Stats.xlsx"
        if not file_path.exists():
            issues.append(f"[SofaScore] Missing file: {file_path}")
            continue

        try:
            df = pd.read_excel(file_path, nrows=5)
        except Exception as exc:
            issues.append(f"[SofaScore] Failed reading {file_path.name}: {exc}")
            continue

        missing = _missing_columns(df, SOFASCORE_REQUIRED_COLUMNS)
        if missing:
            issues.append(f"[SofaScore] {file_path.name} missing columns: {missing}")

        per90_cols = [c for c in df.columns if c.endswith("_per_90")]
        if per90_cols:
            warnings.append(
                f"[SofaScore] {file_path.name} contains derived *_per_90 columns ({len(per90_cols)} cols)."
            )

    return issues, warnings


def validate_fbref(base_dir):
    issues = []
    warnings = []

    for league in LEAGUES:
        file_path = base_dir / f"{league}_Stats.xlsx"
        if not file_path.exists():
            issues.append(f"[FBref] Missing file: {file_path}")
            continue

        try:
            excel = pd.ExcelFile(file_path)
        except Exception as exc:
            issues.append(f"[FBref] Failed opening {file_path.name}: {exc}")
            continue

        for sheet in FBREF_REQUIRED_SHEETS:
            if sheet not in excel.sheet_names:
                issues.append(f"[FBref] {file_path.name} missing required sheet: {sheet}")
                continue
            try:
                df = pd.read_excel(file_path, sheet_name=sheet, nrows=3)
            except Exception as exc:
                issues.append(f"[FBref] Failed reading {file_path.name}::{sheet}: {exc}")
                continue
            missing = _missing_columns(df, FBREF_REQUIRED_COLUMNS[sheet])
            if missing:
                issues.append(f"[FBref] {file_path.name}::{sheet} missing columns: {missing}")

        detailed_present = [s for s in FBREF_DETAILED_SHEETS if s in excel.sheet_names]
        if not detailed_present:
            warnings.append(
                f"[FBref] {file_path.name} has no detailed sheets (shooting/passing/defense/etc)."
            )

    return issues, warnings


def main():
    parser = argparse.ArgumentParser(description="Validate raw schema for SofaScore and FBref outputs.")
    parser.add_argument("--sofascore-dir", default="sofascore_team_data")
    parser.add_argument("--fbref-dir", default="all stats")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warnings as well.",
    )
    args = parser.parse_args()

    sofascore_dir = Path(args.sofascore_dir)
    fbref_dir = Path(args.fbref_dir)

    issues = []
    warnings = []

    sofa_issues, sofa_warnings = validate_sofascore(sofascore_dir)
    fbref_issues, fbref_warnings = validate_fbref(fbref_dir)

    issues.extend(sofa_issues)
    issues.extend(fbref_issues)
    warnings.extend(sofa_warnings)
    warnings.extend(fbref_warnings)

    print("=== RAW Schema Validation ===")
    print(f"Critical issues: {len(issues)}")
    print(f"Warnings: {len(warnings)}")

    if issues:
        print("\n[CRITICAL]")
        for line in issues:
            print(f"- {line}")

    if warnings:
        print("\n[WARNING]")
        for line in warnings:
            print(f"- {line}")

    if issues:
        raise SystemExit(1)
    if args.strict and warnings:
        raise SystemExit(2)

    print("\nValidation passed.")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
