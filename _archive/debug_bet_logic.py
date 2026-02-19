
import json
import update_tracker

def test_logic():
    with open("latest_prediction.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    print("--- Loaded Data ---")
    print("Bet Data keys:", list(data.get("Bet_Data", {}).keys()))
    
    result = update_tracker._best_bet_from_model(data)
    print("\n--- Result from _best_bet_from_model ---")
    print(result)

if __name__ == "__main__":
    test_logic()
