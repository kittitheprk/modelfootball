import subprocess
import sys

def run_prediction(home, away):
    print(f"\n{'='*50}")
    print(f"Testing: {home} vs {away}")
    print(f"{'='*50}")
    # Run the demo script as a subprocess
    result = subprocess.run(
        [sys.executable, "demo_model_v2/run_demo.py", home, away],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("Error running prediction:")
        print(result.stderr)
    else:
        # Print the relevant output parts (skip loading messages)
        output_lines = result.stdout.split('\n')
        printing = False
        for line in output_lines:
            if "Analyzing Match:" in line:
                printing = True
            if printing:
                print(line)

def main():
    matches = [
        ("Cagliari", "Lecce"),
        ("Girona FC", "Barcelona"),
        ("Olympique Lyonnais", "Nice"),
        ("Borussia Dortmund", "Atalanta") # Cross-league test
    ]
    
    for home, away in matches:
        run_prediction(home, away)

if __name__ == "__main__":
    main()
