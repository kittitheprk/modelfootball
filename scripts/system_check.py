import importlib
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REQUIRED_DIRS = [
    "Match Logs",
    "all stats",
    "sofascore_team_data",
    "scripts",
    "tests",
]

REQUIRED_FILES = [
    "analyze_match.py",
    "xg_engine.py",
    "simulator_v9.py",
    "update_tracker.py",
    "scripts/run_update.py",
    "scripts/prepare_dashboard_data.py",
    "tests/test_full_system.py",
    "tests/test_simulator_v9.py",
]

REQUIRED_IMPORTS = [
    "pandas",
    "numpy",
    "requests",
    "openpyxl",
]


def print_status(name, ok, detail=""):
    tag = "OK" if ok else "FAIL"
    if detail:
        print(f"[{tag}] {name}: {detail}")
    else:
        print(f"[{tag}] {name}")


def check_paths():
    ok = True
    for rel_dir in REQUIRED_DIRS:
        path = PROJECT_ROOT / rel_dir
        exists = path.is_dir()
        print_status(f"dir:{rel_dir}", exists, str(path))
        ok = ok and exists

    for rel_file in REQUIRED_FILES:
        path = PROJECT_ROOT / rel_file
        exists = path.is_file()
        print_status(f"file:{rel_file}", exists, str(path))
        ok = ok and exists
    return ok


def check_imports():
    ok = True
    for mod in REQUIRED_IMPORTS:
        try:
            importlib.import_module(mod)
            print_status(f"import:{mod}", True)
        except Exception as exc:
            print_status(f"import:{mod}", False, str(exc))
            ok = False
    return ok


def check_pipeline_preflight():
    try:
        from scripts import run_update
    except Exception as exc:
        print_status("pipeline_preflight", False, f"cannot import scripts.run_update: {exc}")
        return False

    missing = run_update.get_missing_scripts(project_root=PROJECT_ROOT)
    if missing:
        print_status("pipeline_preflight", False, f"missing {len(missing)} script(s)")
        for rel_path, abs_path, desc in missing:
            print(f"  - {rel_path} ({desc}) -> {abs_path}")
        return False

    steps = run_update.build_steps(include_active=False)
    print_status("pipeline_preflight", True, f"{len(steps)} scripts ready")
    return True


def run_smoke_test(timeout_seconds=180):
    test_script = PROJECT_ROOT / "tests" / "test_full_system.py"
    if not test_script.exists():
        print_status("smoke_test", False, f"missing {test_script}")
        return False

    cmd = [sys.executable, str(test_script)]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        print_status("smoke_test", False, f"timeout after {timeout_seconds}s")
        return False
    except Exception as exc:
        print_status("smoke_test", False, str(exc))
        return False

    if result.returncode != 0:
        print_status("smoke_test", False, f"exit={result.returncode}")
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
        return False

    print_status("smoke_test", True, "tests/test_full_system.py passed")
    return True


def check_api_key():
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        print_status("gemini_api_key", True, "GEMINI_API_KEY is set")
        return True

    key_file = PROJECT_ROOT / "gemini_key.txt"
    if key_file.exists():
        try:
            raw = key_file.read_text(encoding="utf-8")
            for line in raw.splitlines():
                cleaned = line.strip().strip('"').strip("'")
                if not cleaned or cleaned.startswith("#"):
                    continue
                if "=" in cleaned:
                    cleaned = cleaned.split("=", 1)[1].strip().strip('"').strip("'")
                if cleaned:
                    print_status("gemini_api_key", True, "loaded from gemini_key.txt")
                    return True
        except Exception as exc:
            print_status("gemini_api_key", True, f"gemini_key.txt found but unreadable: {exc}")
            return True

    print_status("gemini_api_key", True, "not set (AI report steps may fail)")
    return True


def main():
    print("=== System Health Check ===")
    print(f"Project Root: {PROJECT_ROOT}")

    checks = [
        check_paths(),
        check_imports(),
        check_pipeline_preflight(),
        run_smoke_test(),
        check_api_key(),
    ]

    failed = checks.count(False)
    print("\n=== Health Summary ===")
    print(f"Checks Run: {len(checks)}")
    print(f"Failed: {failed}")
    if failed == 0:
        print("System is ready.")
        return 0
    print("System has issues. Please fix failed checks before full automation run.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
