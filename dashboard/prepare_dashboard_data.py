"""
Prepare data for Football Analytics Dashboard
Converts Excel data to JSON format for web application
"""

import pandas as pd
import json
import numpy as np
from pathlib import Path

def load_team_data():
    """Load and process team data from unpivoted_data.xlsx"""
    print("Loading team data...")
    df = pd.read_excel('../charts/unpivoted_data.xlsx')
    
    # Convert to wide format for easier processing
    df_wide = df.pivot_table(
        index=['Team_Name', 'League', 'Team_ID'],
        columns='Metric',
        values='Value',
        aggfunc='first'
    ).reset_index()
    
    # Convert all numeric columns
    for col in df_wide.columns:
        if col not in ['Team_Name', 'League', 'Team_ID']:
            df_wide[col] = pd.to_numeric(df_wide[col], errors='coerce')
    
    # Fill NaN with 0
    df_wide = df_wide.fillna(0)
    
    teams_data = []
    for _, row in df_wide.iterrows():
        team = {
            'name': row['Team_Name'],
            'league': row['League'],
            'id': int(row['Team_ID']),
            'metrics': {}
        }
        
        # Add all metrics
        for col in df_wide.columns:
            if col not in ['Team_Name', 'League', 'Team_ID']:
                team['metrics'][col] = float(row[col]) if not pd.isna(row[col]) else 0
        
        teams_data.append(team)
    
    print(f"Loaded {len(teams_data)} teams")
    return teams_data

def load_player_data():
    """Load and process player data from final_chart_data_long.xlsx"""
    print("Loading player data...")
    df = pd.read_excel('../charts/final_chart_data_long.xlsx')
    
    # Filter out players with very low playing time
    df = df[df['Playing Time_90s'] > 0]
    
    # Group by player to get all their metrics
    players_data = []
    
    for player_name in df['Player'].unique():
        player_df = df[df['Player'] == player_name].iloc[0]
        
        player_metrics = {}
        player_metrics_df = df[df['Player'] == player_name]
        
        for _, metric_row in player_metrics_df.iterrows():
            metric_name = metric_row['Metric']
            player_metrics[metric_name] = {
                'raw': float(metric_row['Raw']) if not pd.isna(metric_row['Raw']) else 0,
                'per90': float(metric_row['Per90']) if not pd.isna(metric_row['Per90']) else 0,
                'percentile': float(metric_row['Percentile']) if not pd.isna(metric_row['Percentile']) else 0
            }
        
        player = {
            'name': player_name,
            'nation': player_df['Nation'] if not pd.isna(player_df['Nation']) else 'Unknown',
            'position': player_df['Pos'] if not pd.isna(player_df['Pos']) else 'Unknown',
            'squad': player_df['Squad'] if not pd.isna(player_df['Squad']) else 'Unknown',
            'league': player_df['League'] if not pd.isna(player_df['League']) else 'Unknown',
            'minutes90s': float(player_df['Playing Time_90s']) if not pd.isna(player_df['Playing Time_90s']) else 0,
            'metrics': player_metrics
        }
        
        players_data.append(player)
    
    print(f"Loaded {len(players_data)} players")
    return players_data

def calculate_percentiles(data, metric_key):
    """Calculate percentiles for a metric across all items"""
    values = [item['metrics'].get(metric_key, 0) for item in data]
    values = [v for v in values if not (isinstance(v, float) and np.isnan(v))]
    
    for item in data:
        value = item['metrics'].get(metric_key, 0)
        if isinstance(value, (int, float)) and not np.isnan(value):
            percentile = sum(1 for v in values if v <= value) / len(values) * 100
            item['metrics'][f'{metric_key}_percentile'] = round(percentile, 2)

def get_available_metrics(teams_data, players_data):
    """Extract all available metrics from the data"""
    team_metrics = set()
    if teams_data:
        for metric in teams_data[0]['metrics'].keys():
            if not metric.endswith('_percentile'):
                team_metrics.add(metric)
    
    player_metrics = set()
    if players_data:
        for metric in players_data[0]['metrics'].keys():
            player_metrics.add(metric)
    
    return {
        'team_metrics': sorted(list(team_metrics)),
        'player_metrics': sorted(list(player_metrics))
    }

def get_leagues(teams_data, players_data):
    """Get unique leagues from the data"""
    leagues = set()
    for team in teams_data:
        leagues.add(team['league'])
    for player in players_data:
        if player['league'] != 'Unknown':
            leagues.add(player['league'])
    return sorted(list(leagues))

def get_positions(players_data):
    """Get unique positions from player data"""
    positions = set()
    for player in players_data:
        pos = player['position']
        if pos and pos != 'Unknown':
            # Extract primary position (first 2 chars)
            if ',' in pos:
                pos = pos.split(',')[0].strip()
            positions.add(pos[:2])
    return sorted(list(positions))

def main():
    print("=" * 50)
    print("Football Analytics Dashboard - Data Preparation")
    print("=" * 50)
    
    # Load data
    teams_data = load_team_data()
    players_data = load_player_data()
    
    # Calculate percentiles for key team metrics
    print("\nCalculating team percentiles...")
    team_metrics_to_rank = ['PPDA', 'FieldTilt_Pct', 'Directness', 'OPPDA']
    for metric in team_metrics_to_rank:
        if teams_data and metric in teams_data[0]['metrics']:
            calculate_percentiles(teams_data, metric)
    
    # Get metadata
    print("\nExtracting metadata...")
    leagues = get_leagues(teams_data, players_data)
    positions = get_positions(players_data)
    available_metrics = get_available_metrics(teams_data, players_data)
    
    # Prepare final data structure
    dashboard_data = {
        'metadata': {
            'generated_at': pd.Timestamp.now().isoformat(),
            'total_teams': len(teams_data),
            'total_players': len(players_data),
            'leagues': leagues,
            'positions': positions,
            'available_metrics': available_metrics
        },
        'teams': teams_data,
        'players': players_data
    }
    
    # Save to JSON
    output_path = Path('data.json')
    print(f"\nSaving data to {output_path}...")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dashboard_data, f, ensure_ascii=False, indent=2)
    
    # Print summary
    print("\n" + "=" * 50)
    print("Data preparation complete!")
    print("=" * 50)
    print(f"Teams: {len(teams_data)}")
    print(f"Players: {len(players_data)}")
    print(f"Leagues: {', '.join(leagues)}")
    print(f"Positions: {', '.join(positions)}")
    print(f"Team Metrics: {len(available_metrics['team_metrics'])}")
    print(f"Player Metrics: {len(available_metrics['player_metrics'])}")
    print(f"\nOutput file: {output_path.absolute()}")
    print(f"File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
    print("=" * 50)

if __name__ == "__main__":
    main()
