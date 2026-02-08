import sys
import os
import time
import subprocess

# Force UTF-8 for stdout to handle Thai characters
sys.stdout.reconfigure(encoding='utf-8')

# Configuration for Scripts to Run
# Using relative paths from the root where this script is located
SCRIPTS_TO_RUN = [
    (r"all stats\scrape_all_stats.py", "Scraping Base League Stats..."),
    (r"sofascore_team_data\scrape_sofascore.py", "Scraping SofaScore Team Data..."),
    (r"scrape_heatmaps.py", "Scraping Player Season Heatmaps..."),
    (r"scrape_sofaplayer.py", "Scraping Detailed Player Season Stats..."),
    (r"create_game_flow.py", "Calculating Game Flow Metrics..."),
    (r"all stats\scrape_detailed_stats.py", "Scraping Detailed Stats (Shooting, Passing, etc.)..."),
    (r"Match Logs\scrape_match_logs.py", "Scraping Match Logs..."),
    (r"charts\process_chart_data.py", "Processing Data for Charts..."),
    (r"charts\create_long_format_data.py", "Creating Final Long Format Data (Excel)..."),
    (r"prepare_dashboard_data.py", "Updating Dashboard Data (data.json)...")
]

def run_scripts():
    print("=== Starting Headless Automation Pipeline ===")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    total = len(SCRIPTS_TO_RUN)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    for index, (script_rel_path, description) in enumerate(SCRIPTS_TO_RUN):
        script_path = os.path.join(current_dir, script_rel_path)
        
        print(f"\n[{index+1}/{total}] {description}")
        print(f"Script: {script_path}")
        
        if not os.path.exists(script_path):
            print(f"ERROR: File not found: {script_path}")
            continue

        try:
            # Run subprocess and stream output
            # buffer=0 for unbuffered output
            process = subprocess.Popen(
                [sys.executable, "-u", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                cwd=current_dir,
                bufsize=1
            )
            
            # Print output in real-time
            for line in process.stdout:
                print(f"  > {line}", end='')
            
            process.wait()
            
            if process.returncode != 0:
                print(f"  [!] Script exited with code {process.returncode}")
                # We do not stop the pipeline, we try to continue
            else:
                print("  [OK] Completed successfully.")
                
        except KeyboardInterrupt:
            print("\nPipeline interrupted by user.")
            sys.exit(1)
        except Exception as e:
            print(f"EXCEPTION running {script_rel_path}: {e}")

    print("\n=== Pipeline Completed ===")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    run_scripts()
