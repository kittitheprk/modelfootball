
from xg_engine import XGEngine

def test_lookup():
    # Initialize with Ligue 1
    engine = XGEngine("Ligue_1")
    
    # Test AS Monaco (Should map to Monaco.xlsx)
    print("Testing 'AS Monaco'...")
    stats = engine.get_team_rolling_stats("AS Monaco")
    if stats:
        print(" [SUCCESS] Found stats for AS Monaco:")
        print(stats)
    else:
        print(" [FAILURE] Could not find stats for AS Monaco.")

    # Test PSG (Should map to Paris Saint-Germain.xlsx via exact match or alias)
    print("\nTesting 'Paris Saint-Germain'...")
    stats_psg = engine.get_team_rolling_stats("Paris Saint-Germain")
    if stats_psg:
        print(" [SUCCESS] Found stats for PSG:")
    else:
        print(" [FAILURE] Could not find stats for PSG.")

if __name__ == "__main__":
    test_lookup()
