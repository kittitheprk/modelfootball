import tkinter as tk
from tkinter import scrolledtext
import subprocess
import threading
import sys
import os

# Configuration for Scripts to Run
# Using relative paths from the root where this script is located
SCRIPTS_TO_RUN = [
    (r"all stats\scrape_all_stats.py", "Scraping Base League Stats..."),
    (r"sofascore_team_data\scrape_sofascore.py", "Scraping SofaScore Team Data..."),
    (r"scrape_sofaplayer.py", "Scraping Detailed Player Season Stats..."),
    (r"create_game_flow.py", "Calculating Game Flow Metrics..."),
    (r"all stats\scrape_detailed_stats.py", "Scraping Detailed Stats (Shooting, Passing, etc.)..."),
    (r"Match Logs\scrape_match_logs.py", "Scraping Match Logs..."),
    (r"charts\process_chart_data.py", "Processing Data for Charts..."),
    (r"charts\create_long_format_data.py", "Creating Final Long Format Data (Excel)...")
]

class ScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Football Data Automation Pipeline")
        self.root.geometry("800x600")
        
        # Header
        self.label = tk.Label(root, text="Football Data Scraper & Processor", font=("Arial", 16, "bold"))
        self.label.pack(pady=10)
        
        # Status Label
        self.status_label = tk.Label(root, text="Ready", font=("Arial", 10), fg="blue")
        self.status_label.pack(pady=5)

        # Scrolled Text Area for Logs
        self.log_area = scrolledtext.ScrolledText(root, width=90, height=25, font=("Consolas", 9))
        self.log_area.pack(pady=10, padx=10)
        self.log_area.config(state=tk.DISABLED) # Read-only initially

        # Button Frame
        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(pady=10)

        # Start Button
        self.start_btn = tk.Button(self.btn_frame, text="Start Pipeline", command=self.start_pipeline, 
                                   bg="#4CAF50", fg="white", font=("Arial", 12, "bold"), width=15)
        self.start_btn.pack(side=tk.LEFT, padx=20)
        
        # Close Button
        self.close_btn = tk.Button(self.btn_frame, text="Close", command=root.quit, 
                                   bg="#f44336", fg="white", font=("Arial", 12, "bold"), width=10)
        self.close_btn.pack(side=tk.LEFT, padx=20)

        self.is_running = False

    def log(self, message):
        """Thread-safe logging to the text area."""
        self.root.after(0, self._append_log, message)

    def _append_log(self, message):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END) # Auto-scroll
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
        self.log_area.delete(1.0, tk.END) # Clear logs
        self.log_area.config(state=tk.DISABLED)
        
        # Start worker thread
        thread = threading.Thread(target=self.run_scripts)
        thread.start()

    def run_scripts(self):
        self.log("=== Starting Automation Pipeline ===")
        total = len(SCRIPTS_TO_RUN)
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        for index, (script_rel_path, description) in enumerate(SCRIPTS_TO_RUN):
            script_path = os.path.join(current_dir, script_rel_path)
            
            self.set_status(f"Step {index+1}/{total}: {description}", "#e65100") # Orange
            self.log(f"\n[{index+1}/{total}] {description}")
            self.log(f"Running: {script_path}...")
            
            if not os.path.exists(script_path):
                self.log(f"ERROR: File not found: {script_path}")
                self.set_status("Failed", "red")
                self.is_running = False
                self.toggle_buttons(True)
                return

            try:
                # Use subproccess to capture output
                # python -u forces unbuffered output so we see it real-time
                process = subprocess.Popen(
                    [sys.executable, "-u", script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    cwd=current_dir # Run from root
                )
                
                # Stream logs
                for line in process.stdout:
                    self.log(line.strip())
                
                process.wait()
                
                if process.returncode != 0:
                    self.log(f"ERROR: Script exited with code {process.returncode}")
                    self.set_status("Pipeline Failed", "red")
                    self.is_running = False
                    self.toggle_buttons(True)
                    return
                    
            except Exception as e:
                self.log(f"EXCEPTION: {e}")
                self.set_status("Error", "red")
                self.is_running = False
                self.toggle_buttons(True)
                return

        self.log("\n=== Pipeline Completed Successfully! ===")
        self.set_status("Success! All data updated.", "green")
        self.is_running = False
        self.toggle_buttons(True)

if __name__ == "__main__":
    root = tk.Tk()
    app = ScraperApp(root)
    
    if "--auto-start" in sys.argv:
        root.after(1000, app.start_pipeline)
        
    root.mainloop()
