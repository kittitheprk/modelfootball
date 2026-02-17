import argparse
import subprocess
import sys
import time
from pathlib import Path

# Force UTF-8 for stdout to handle Thai characters
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Script paths are relative to project root
SCRIPTS_TO_RUN = [
    ("all stats/scrape_all_stats.py", "Scraping Base League Stats..."),
    ("sofascore_team_data/scrape_sofascore.py", "Scraping SofaScore Team Data..."),
    ("scripts/scrape_heatmaps.py", "Scraping Player Season Heatmaps..."),
    ("scripts/scrape_sofaplayer.py", "Scraping Detailed Player Season Stats..."),
    ("scripts/create_game_flow.py", "Calculating Game Flow Metrics..."),
    ("all stats/scrape_detailed_stats.py", "Scraping Detailed Stats (Shooting, Passing, etc.)..."),
    ("Match Logs/scrape_match_logs.py", "Scraping Match Logs..."),
    ("charts/process_chart_data.py", "Processing Data for Charts..."),
    ("charts/create_long_format_data.py", "Creating Final Long Format Data (Excel)..."),
    ("scripts/prepare_dashboard_data.py", "Updating Dashboard Data (data.json)..."),
]


def resolve_step_path(relative_script_path, project_root=PROJECT_ROOT):
    return (project_root / Path(relative_script_path)).resolve()


def get_missing_scripts(steps=SCRIPTS_TO_RUN, project_root=PROJECT_ROOT):
    missing = []
    for rel_path, description in steps:
        script_path = resolve_step_path(rel_path, project_root=project_root)
        if not script_path.exists():
            missing.append((rel_path, str(script_path), description))
    return missing


def run_single_script(script_path, description, cwd):
    start = time.time()
    process = subprocess.Popen(
        [sys.executable, "-u", str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        cwd=str(cwd),
        bufsize=1,
    )
    if process.stdout is not None:
        for line in process.stdout:
            print(f"  > {line}", end="")
    process.wait()
    return process.returncode, time.time() - start


def run_scripts(continue_on_error=False, dry_run=False, preflight_only=False):
    print("=== Starting Headless Automation Pipeline ===")
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    missing = get_missing_scripts()
    if missing:
        print("\n[Preflight] Missing scripts detected:")
        for rel_path, abs_path, description in missing:
            print(f"  - {rel_path} ({description})")
            print(f"    Expected at: {abs_path}")
        print("\nPreflight failed.")
        return 2

    print(f"\n[Preflight] OK: {len(SCRIPTS_TO_RUN)} scripts found.")

    if dry_run:
        print("\n[Dry Run] Pipeline steps:")
        for idx, (rel_path, description) in enumerate(SCRIPTS_TO_RUN, start=1):
            print(f"  {idx:02d}. {description} -> {rel_path}")
        return 0

    if preflight_only:
        return 0

    results = []
    total = len(SCRIPTS_TO_RUN)
    for index, (script_rel_path, description) in enumerate(SCRIPTS_TO_RUN, start=1):
        script_path = resolve_step_path(script_rel_path)
        print(f"\n[{index}/{total}] {description}")
        print(f"Script: {script_path}")
        try:
            returncode, duration = run_single_script(script_path, description, cwd=PROJECT_ROOT)
        except KeyboardInterrupt:
            print("\nPipeline interrupted by user.")
            return 130
        except Exception as exc:
            print(f"[!] Exception while running {script_rel_path}: {exc}")
            returncode = 1
            duration = 0.0

        ok = returncode == 0
        status = "OK" if ok else "FAILED"
        print(f"  [{status}] exit={returncode} time={duration:.1f}s")
        results.append((script_rel_path, description, returncode, duration))
        if not ok and not continue_on_error:
            print("\nStopping pipeline due to failure (use --continue-on-error to keep going).")
            break

    ok_count = sum(1 for _, _, code, _ in results if code == 0)
    fail_count = len(results) - ok_count
    print("\n=== Pipeline Summary ===")
    print(f"Completed Steps: {len(results)}/{len(SCRIPTS_TO_RUN)}")
    print(f"Successful: {ok_count}")
    print(f"Failed: {fail_count}")
    print(f"End Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    return 0 if fail_count == 0 and len(results) == len(SCRIPTS_TO_RUN) else 1


def parse_args():
    parser = argparse.ArgumentParser(description="Headless data update pipeline")
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue running remaining steps even if one step fails.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show pipeline steps after preflight checks without executing scripts.",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate required scripts and exit.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exit_code = run_scripts(
        continue_on_error=args.continue_on_error,
        dry_run=args.dry_run,
        preflight_only=args.preflight_only,
    )
    sys.exit(exit_code)
