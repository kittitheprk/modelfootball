import os
import sys
import unittest
import subprocess
import json
import shutil

# Ensure we can import local modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

class TestCLIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a backup of critical files before running destructive tests
        cls.tracker_file = os.path.join(PROJECT_ROOT, "prediction_tracker.xlsx")
        cls.backup_tracker = os.path.join(PROJECT_ROOT, "prediction_tracker.xlsx.bak")
        if os.path.exists(cls.tracker_file):
            shutil.copy2(cls.tracker_file, cls.backup_tracker)
            
        cls.json_file = os.path.join(PROJECT_ROOT, "latest_prediction.json")
        cls.backup_json = os.path.join(PROJECT_ROOT, "latest_prediction.json.bak")
        if os.path.exists(cls.json_file):
            shutil.copy2(cls.json_file, cls.backup_json)

    @classmethod
    def tearDownClass(cls):
        # Restore backups
        if os.path.exists(cls.backup_tracker):
            shutil.move(cls.backup_tracker, cls.tracker_file)
        if os.path.exists(cls.backup_json):
            shutil.move(cls.backup_json, cls.json_file)

    def test_analyze_match_script(self):
        """Test the analyze_match.py script runs efficiently without error."""
        cmd = [sys.executable, "analyze_match.py", "Arsenal", "Liverpool"]
        
        # Run the command
        result = subprocess.run(
            cmd, 
            cwd=PROJECT_ROOT, 
            capture_output=True, 
            text=True,
            timeout=120  # 2 minute timeout
        )
        
        # Check exit code
        self.assertEqual(result.returncode, 0, f"Script failed with stderr: {result.stderr}")
        
        # Check output file generation
        latest_json = os.path.join(PROJECT_ROOT, "latest_prediction.json")
        self.assertTrue(os.path.exists(latest_json), "latest_prediction.json was not created")
        
        with open(latest_json, "r") as f:
            data = json.load(f)
            
        # Basic validation of JSON content
        self.assertIn("Match", data)
        self.assertIn("Pred_Home_Win", data)
        self.assertIn("Bet_Data", data)
        
        # Check if analysis markdown was generated (file name might vary based on input)
        # We expect 'analyses/analysis_Arsenal_Liverpool.md' or similar
        analysis_dir = os.path.join(PROJECT_ROOT, "analyses")
        found_md = False
        for fname in os.listdir(analysis_dir):
            if "Arsenal" in fname and "Liverpool" in fname and fname.endswith(".md"):
                found_md = True
                break
        
        # Note: If no API key, MD might not be generated. Depending on test env.
        # So we might warn instead of fail if missing, or check logic.
        # But for full system verifiction, we assume it should work if configured.
        if os.environ.get("GEMINI_API_KEY") or os.path.exists(os.path.join(PROJECT_ROOT, "gemini_key.txt")):
             self.assertTrue(found_md, "Analysis Markdown file was not created in analyses/")

if __name__ == "__main__":
    unittest.main()
