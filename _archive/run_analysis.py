import pandas as pd
import simulator
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

def get_sim_stats(team, league):
    filename = f'sofascore_team_data/{league}_Team_Stats.xlsx'
    if os.path.exists(filename):
        df = pd.read_excel(filename)
        row = df[df['Team_Name'].str.contains(team, case=False, na=False)]
        if not row.empty:
            return {
                'goals_scored_per_game': row.iloc[0]['goalsScored_per_90'],
                'goals_conceded_per_game': row.iloc[0]['goalsConceded_per_90']
            }
    return None

def get_avgs(league):
    filename = f'sofascore_team_data/{league}_Team_Stats.xlsx'
    if os.path.exists(filename):
        df = pd.read_excel(filename)
        avg = df['goalsScored_per_90'].mean()
        return {'avg_goals_home': avg * 1.1, 'avg_goals_away': avg * 0.9}
    return {'avg_goals_home': 1.5, 'avg_goals_away': 1.2}

def get_game_flow(team, league):
    filename = f'game flow/{league}_GameFlow.xlsx'
    if os.path.exists(filename):
        df = pd.read_excel(filename)
        row = df[df['Team_Name'].str.contains(team, case=False, na=False)]
        if not row.empty:
            return row.iloc[0].to_dict()
    return {}

matches = [
    ('Valencia', 'Real Madrid', 'La_Liga'),
    ('Paris Saint-Germain', 'Marseille', 'Ligue_1'),
    ('Juventus', 'Lazio', 'Serie_A')
]

for home, away, league in matches:
    print(f'\n{"="*60}')
    print(f'  {home} vs {away} ({league})')
    print(f'{"="*60}')
    
    h_sim = get_sim_stats(home, league)
    a_sim = get_sim_stats(away, league)
    h_flow = get_game_flow(home, league)
    a_flow = get_game_flow(away, league)
    
    if h_sim and a_sim:
        avgs = get_avgs(league)
        result = simulator.simulate_match(home, away, h_sim, a_sim, avgs, iterations=300)
        
        print(f'\n📊 Simulation Results (300 iterations):')
        print(f'   {home} Win: {result["home_win_prob"]:.1f}%')
        print(f'   Draw: {result["draw_prob"]:.1f}%')
        print(f'   {away} Win: {result["away_win_prob"]:.1f}%')
        print(f'   ⚽ Most Likely Score: {result["most_likely_score"]}')
        
        print(f'\n📈 Team Stats:')
        print(f'   {home}: Goals/90: {h_sim["goals_scored_per_game"]:.2f}, Conceded/90: {h_sim["goals_conceded_per_game"]:.2f}')
        print(f'   {away}: Goals/90: {a_sim["goals_scored_per_game"]:.2f}, Conceded/90: {a_sim["goals_conceded_per_game"]:.2f}')
        
        if h_flow and a_flow:
            print(f'\n📉 Game Flow (PPDA):')
            h_ppda = h_flow.get('calc_PPDA', 'N/A')
            a_ppda = a_flow.get('calc_PPDA', 'N/A')
            if h_ppda != 'N/A':
                print(f'   {home}: PPDA {h_ppda:.2f}')
            if a_ppda != 'N/A':
                print(f'   {away}: PPDA {a_ppda:.2f}')
    else:
        print(f'Could not find data for teams')

print(f'\n{"="*60}')
print('Analysis Complete!')
