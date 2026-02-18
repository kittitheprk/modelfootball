import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import update_football_data as main_pipeline


def resolve_step_path(relative_script_path, project_root=PROJECT_ROOT):
    return main_pipeline.resolve_step_path(relative_script_path, project_root=project_root)


def build_steps(include_active=False):
    return main_pipeline.build_steps(include_active=include_active)


def get_missing_scripts(steps=None, project_root=PROJECT_ROOT):
    return main_pipeline.get_missing_scripts(steps=steps, project_root=project_root)


def run_scripts(continue_on_error=False, dry_run=False, preflight_only=False, include_active=False):
    return main_pipeline.run_pipeline(
        continue_on_error=continue_on_error,
        dry_run=dry_run,
        preflight_only=preflight_only,
        include_active=include_active,
        project_root=PROJECT_ROOT,
        log_callback=print,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Headless data update pipeline (wrapper)")
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
    parser.add_argument(
        "--include-active",
        action="store_true",
        help="Run derived/converted ACTIVE scripts after RAW scraping.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(
        run_scripts(
            continue_on_error=args.continue_on_error,
            dry_run=args.dry_run,
            preflight_only=args.preflight_only,
            include_active=args.include_active,
        )
    )
