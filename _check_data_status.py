import os, datetime

base = '.'
dirs = {
    'all stats': ['all stats'],
    'Match Logs (PL)': ['Match Logs/Premier_League'],
    'Match Logs (SerA)': ['Match Logs/Serie_A'],
    'Match Logs (LaLiga)': ['Match Logs/La_Liga'],
    'Match Logs (L1)': ['Match Logs/Ligue_1'],
    'Match Logs (Bund)': ['Match Logs/Bundesliga'],
    'heatmap': ['heatmap'],
    'sofaplayer': ['sofaplayer'],
    'sofascore_team_data': ['sofascore_team_data'],
    'player_characteristics': ['player_characteristics'],
    'charts': ['charts'],
    'game_flow': ['game_flow'],
}

print("=" * 90)
print("FOOTBALL DATABASE STATUS CHECK")
print("=" * 90)

for name, paths in dirs.items():
    latest = None
    latest_file = ''
    count = 0
    for d in paths:
        p = os.path.join(base, d)
        if not os.path.exists(p):
            continue
        for f in os.listdir(p):
            fp = os.path.join(p, f)
            if os.path.isfile(fp) and not f.startswith('.') and not f.endswith('.py'):
                count += 1
                mt = os.path.getmtime(fp)
                if latest is None or mt > latest:
                    latest = mt
                    latest_file = f
    if latest:
        dt = datetime.datetime.fromtimestamp(latest)
        age = (datetime.datetime.now() - dt).days
        status = "UP TO DATE" if age <= 3 else ("OUTDATED" if age > 7 else "NEEDS UPDATE")
        emoji = "[OK]" if age <= 3 else ("[!!]" if age > 7 else "[!]")
        print(f"  {emoji} {name:<25} | {count:>4} files | Updated: {dt.strftime('%Y-%m-%d %H:%M')} ({age}d ago) | {latest_file}")
    else:
        print(f"  [??] {name:<25} | NOT FOUND")

print("=" * 90)
