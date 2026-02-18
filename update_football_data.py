import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import scrolledtext
except Exception:
    tk = None
    scrolledtext = None


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PROJECT_ROOT = Path(__file__).resolve().parent

# This file is now the single source of truth for pipeline steps.
RAW_SCRIPTS_TO_RUN = [
    ("all stats/scrape_all_stats.py", "Scraping Base League Stats..."),
    ("all stats/scrape_detailed_stats.py", "Scraping Detailed Stats (Shooting, Passing, etc.)..."),
    ("sofascore_team_data/scrape_sofascore.py", "Scraping SofaScore Team Data (raw only)..."),
    ("scripts/scrape_sofaplayer.py", "Scraping Detailed Player Season Stats..."),
    ("Match Logs/scrape_match_logs.py", "Scraping Match Logs..."),
    ("scripts/validate_raw_columns.py", "Validating RAW columns against expected schema..."),
]

ACTIVE_SCRIPTS_TO_RUN = [
    ("active/convert_sofascore_per90.py", "Creating SofaScore per90 derived files..."),
    ("scripts/create_game_flow.py", "Calculating Game Flow Metrics..."),
    ("scripts/prepare_dashboard_data.py", "Updating Dashboard Data (data.json)..."),
]

DEFAULT_RUN_ACTIVE_SCRIPTS = False


def build_steps(include_active=False):
    if include_active:
        return RAW_SCRIPTS_TO_RUN + ACTIVE_SCRIPTS_TO_RUN
    return list(RAW_SCRIPTS_TO_RUN)


def resolve_step_path(relative_script_path, project_root=PROJECT_ROOT):
    return (project_root / Path(relative_script_path)).resolve()


def get_missing_scripts(steps=None, project_root=PROJECT_ROOT):
    if steps is None:
        steps = build_steps(include_active=DEFAULT_RUN_ACTIVE_SCRIPTS)
    missing = []
    for rel_path, description in steps:
        script_path = resolve_step_path(rel_path, project_root=project_root)
        if not script_path.exists():
            missing.append((rel_path, str(script_path), description))
    return missing


def _run_single_script(script_path, cwd, log_callback):
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
            log_callback(f"  > {line.rstrip()}")
    process.wait()
    return process.returncode, time.time() - start


def run_pipeline(
    continue_on_error=False,
    dry_run=False,
    preflight_only=False,
    include_active=False,
    project_root=PROJECT_ROOT,
    log_callback=print,
):
    steps = build_steps(include_active=include_active)
    mode_text = "RAW + ACTIVE" if include_active else "RAW ONLY"

    log_callback("=== Starting Automation Pipeline ===")
    log_callback(f"Project Root: {project_root}")
    log_callback(f"Start Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_callback(f"Mode: {mode_text}")

    missing = get_missing_scripts(steps=steps, project_root=project_root)
    if missing:
        log_callback("\n[Preflight] Missing scripts detected:")
        for rel_path, abs_path, description in missing:
            log_callback(f"  - {rel_path} ({description})")
            log_callback(f"    Expected at: {abs_path}")
        log_callback("\nPreflight failed.")
        return 2

    log_callback(f"\n[Preflight] OK: {len(steps)} scripts found.")

    if dry_run:
        log_callback("\n[Dry Run] Pipeline steps:")
        for idx, (rel_path, description) in enumerate(steps, start=1):
            log_callback(f"  {idx:02d}. {description} -> {rel_path}")
        return 0

    if preflight_only:
        return 0

    results = []
    total = len(steps)
    for index, (script_rel_path, description) in enumerate(steps, start=1):
        script_path = resolve_step_path(script_rel_path, project_root=project_root)
        log_callback(f"\n[{index}/{total}] {description}")
        log_callback(f"Script: {script_path}")
        try:
            returncode, duration = _run_single_script(script_path, cwd=project_root, log_callback=log_callback)
        except KeyboardInterrupt:
            log_callback("\nPipeline interrupted by user.")
            return 130
        except Exception as exc:
            log_callback(f"[!] Exception while running {script_rel_path}: {exc}")
            returncode = 1
            duration = 0.0

        ok = returncode == 0
        status = "OK" if ok else "FAILED"
        log_callback(f"  [{status}] exit={returncode} time={duration:.1f}s")
        results.append((script_rel_path, description, returncode, duration))
        if not ok and not continue_on_error:
            log_callback("\nStopping pipeline due to failure (use --continue-on-error to keep going).")
            break

    ok_count = sum(1 for _, _, code, _ in results if code == 0)
    fail_count = len(results) - ok_count
    log_callback("\n=== Pipeline Summary ===")
    log_callback(f"Completed Steps: {len(results)}/{len(steps)}")
    log_callback(f"Successful: {ok_count}")
    log_callback(f"Failed: {fail_count}")
    log_callback(f"End Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    return 0 if fail_count == 0 and len(results) == len(steps) else 1


class ScraperApp:
    def __init__(self, root, include_active=DEFAULT_RUN_ACTIVE_SCRIPTS):
        self.root = root
        self.include_active = include_active
        self.root.title("Football Data Automation Pipeline")
        self.root.geometry("800x600")

        self.label = tk.Label(root, text="Football Data Scraper & Processor", font=("Arial", 16, "bold"))
        self.label.pack(pady=10)

        self.status_label = tk.Label(root, text="Ready", font=("Arial", 10), fg="blue")
        self.status_label.pack(pady=5)

        self.log_area = scrolledtext.ScrolledText(root, width=90, height=25, font=("Consolas", 9))
        self.log_area.pack(pady=10, padx=10)
        self.log_area.config(state=tk.DISABLED)

        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(pady=10)

        self.start_btn = tk.Button(
            self.btn_frame,
            text="Start Pipeline",
            command=self.start_pipeline,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 12, "bold"),
            width=15,
        )
        self.start_btn.pack(side=tk.LEFT, padx=20)

        self.close_btn = tk.Button(
            self.btn_frame,
            text="Close",
            command=root.quit,
            bg="#f44336",
            fg="white",
            font=("Arial", 12, "bold"),
            width=10,
        )
        self.close_btn.pack(side=tk.LEFT, padx=20)

        self.is_running = False

    def log(self, message):
        self.root.after(0, self._append_log, message)

    def _append_log(self, message):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)

    def set_status(self, message, color="blue"):
        self.root.after(0, lambda: self.status_label.config(text=message, fg=color))

    def toggle_buttons(self, enable):
        state = tk.NORMAL if enable else tk.DISABLED
        self.root.after(0, lambda: self.start_btn.config(state=state))

    def start_pipeline(self):
        if self.is_running:
            return
        self.is_running = True
        self.toggle_buttons(False)
        self.log_area.config(state=tk.NORMAL)
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state=tk.DISABLED)
        thread = threading.Thread(target=self.run_scripts)
        thread.start()

    def run_scripts(self):
        mode_text = "RAW + ACTIVE" if self.include_active else "RAW ONLY"
        self.log(f"Mode: {mode_text}")

        def gui_logger(message):
            self.log(message)
            if message.startswith("[") and "/" in message:
                self.set_status(message, "#e65100")
            elif "FAILED" in message or "Missing scripts" in message:
                self.set_status("Pipeline Failed", "red")

        exit_code = run_pipeline(
            include_active=self.include_active,
            project_root=PROJECT_ROOT,
            log_callback=gui_logger,
        )

        if exit_code == 0:
            self.log("\n=== Pipeline Completed Successfully! ===")
            self.set_status("Success! All data updated.", "green")
        else:
            self.set_status("Pipeline Failed", "red")
        self.is_running = False
        self.toggle_buttons(True)


def parse_args():
    parser = argparse.ArgumentParser(description="Football data pipeline (GUI + headless)")
    parser.add_argument("--headless", action="store_true", help="Run pipeline in terminal mode.")
    parser.add_argument("--auto-start", action="store_true", help="Auto-start pipeline when GUI opens.")
    parser.add_argument(
        "--include-active",
        action="store_true",
        help="Run ACTIVE transforms after RAW scraping.",
    )
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


def launch_gui(auto_start=False, include_active=DEFAULT_RUN_ACTIVE_SCRIPTS):
    if tk is None:
        print("Tkinter is not available in this environment. Use --headless mode.")
        return 3
    root = tk.Tk()
    app = ScraperApp(root, include_active=include_active)
    if auto_start:
        root.after(1000, app.start_pipeline)
    root.mainloop()
    return 0


if __name__ == "__main__":
    args = parse_args()

    headless_mode = (
        args.headless
        or args.dry_run
        or args.preflight_only
        or args.continue_on_error
    )

    if headless_mode:
        raise SystemExit(
            run_pipeline(
                continue_on_error=args.continue_on_error,
                dry_run=args.dry_run,
                preflight_only=args.preflight_only,
                include_active=args.include_active,
                project_root=PROJECT_ROOT,
                log_callback=print,
            )
        )
    raise SystemExit(launch_gui(auto_start=args.auto_start, include_active=args.include_active))
