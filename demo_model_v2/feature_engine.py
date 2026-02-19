import pandas as pd
import numpy as np
import math

class FeatureEngine:
    def __init__(self, data_loader=None):
        self.data_loader = data_loader

    def calculate_feature_metrics(self, df):
        """
        Calculates advanced metrics from raw stats.
        """
        # 1. Attack Strength (Relative to League Average)
        # We use xG per game / League Average xG per game
        league_avg_xg = df['expected_goals'].mean()
        df['attack_strength'] = df['expected_goals'] / league_avg_xg
        
        # 2. Defense Strength
        # Opta Definition: xGA (Expected Goals Against)
        # Since we might not have direct xGA, we approximate it.
        # Approximation: Logic - A team's defense strength is inversely proportional 
        # to the goals/xG they concede.
        # But wait, we need 'goals_conceded' or 'xGA'.
        if 'goalsconceded' in df.columns: # Cleaned names are lowercase
             league_avg_conceded = df['goalsconceded'].mean()
             df['defense_strength'] = df['goalsconceded'] / league_avg_conceded
        elif 'goals_conceded' in df.columns:
             league_avg_conceded = df['goals_conceded'].mean()
             df['defense_strength'] = df['goals_conceded'] / league_avg_conceded
        else:
            # Fallback if no conceded column (unlikely)
            df['defense_strength'] = 1.0


        # 3. Creativity Metrics (xA & Key Passes)
        # If xA is missing, we use Key Passes as a proxy for "Creativity Factor"
        if 'expected_assists' in df.columns:
            df['creativity_rating'] = df['expected_assists'] / df['expected_assists'].mean()
        elif 'key_passes' in df.columns: 
             df['creativity_rating'] = df['key_passes'] / df['key_passes'].mean()
        elif 'keypasses' in df.columns:
             df['creativity_rating'] = df['keypasses'] / df['keypasses'].mean()
        else:
             df['creativity_rating'] = 1.0

        # 4. Possession & Dominance
        # 'average_possession' or 'possession_percentage' might be in the raw data 
        # (needs check, but we can use 'accurate_passes' as proxy for control)
        if 'accurate_passes' in df.columns: # check cleaned name
             df['dominance_rating'] = df['accurate_passes'] / df['accurate_passes'].mean()
        elif 'accuratepasses' in df.columns:
             df['dominance_rating'] = df['accuratepasses'] / df['accuratepasses'].mean()
        else:
             df['dominance_rating'] = 1.0

        return df

    def _calculate_weighted_ratings(self, team_name, match_log_loader, season_stats_df=None, venue_filter=None):
        """
        Calculates ratings based on recent match logs using exponential time-decay.
        Also adjusts for Opponent Strength if season_stats_df is provided.
        Can filter by venue ('Home' or 'Away').
        """
        df_log = match_log_loader.load_match_log(team_name)
        
        if df_log is None or df_log.empty:
            return None
            
        # Filter by Venue if requested
        if venue_filter:
             # Normalize venue strings. Log usually has 'Home' or 'Away'.
             # df_log['Venue'] should be 'Home' or 'Away' (from loader)
             df_log = df_log[df_log['Venue'] == venue_filter].copy()
             
             if df_log.empty:
                 return None
            
        # Exponential Decay Parameters
        alpha = 0.05 # Decay rate
        
        # Calculate weights
        weights = []
        weighted_xg_sum = 0
        weighted_xga_sum = 0
        weight_sum = 0
        
        # Pre-compute average ratings for normalization/adjustment
        league_avg_attack = 1.0
        league_avg_defense = 1.0
        
        # We iterate through the filtered log.
        # Note: 'matches_ago' should arguably be 'games ago AT THIS VENUE' if we filter.
        # Iterating on the filtered DF effectively does this (i=0 is last home game).
        for i, row in df_log.iterrows():
            matches_ago = i # 0 = most recent match in this set
            weight = math.exp(-alpha * matches_ago)
            
            xG = row['xG']
            xGA = row['xGA']
            opponent_name = row['Opponent']
            
            # Opponent Strength Adjustment
            opp_def_strength = 1.0
            opp_att_strength = 1.0
            
            if season_stats_df is not None:
                try:
                   opp_stats = season_stats_df[season_stats_df['team_name'] == opponent_name]
                   if not opp_stats.empty:
                       opp_def_strength = opp_stats.iloc[0].get('defense_strength', 1.0)
                       opp_att_strength = opp_stats.iloc[0].get('attack_strength', 1.0)
                except Exception:
                    pass 
            
            adjusted_xg = xG / opp_def_strength
            adjusted_xga = xGA / opp_att_strength
            
            weighted_xg_sum += adjusted_xg * weight
            weighted_xga_sum += adjusted_xga * weight
            weight_sum += weight
            
        if weight_sum == 0:
            return None
            
        avg_weighted_xg = weighted_xg_sum / weight_sum
        avg_weighted_xga = weighted_xga_sum / weight_sum
        
        # Normalize
        league_baseline = 1.5 
        
        return {
            'attack': avg_weighted_xg / league_baseline,
            'defense': avg_weighted_xga / league_baseline,
            'expected_goals_avg': avg_weighted_xg
        }

    def get_team_ratings(self, df, team_name, match_log_loader=None, venue=None, player_tax=None):
        """
        Returns a dictionary of ratings for a specific team.
        Prioritizes weighted ratings (Time-Decay + Opponent Adj + Home/Away) from match logs.
        player_tax: Dict {'attack_tax': float, 'defense_tax': float} (Multiplier, e.g. 0.9 = 10% drop)
        """
        
        ratings = None
        source_label = "Season Average"
        
        # 1. Try Time-Decay (Weighted) Ratings First
        if match_log_loader:
             weighted_rating = self._calculate_weighted_ratings(
                team_name, 
                match_log_loader, 
                season_stats_df=df,
                venue_filter=venue
            )
             if weighted_rating:
                 season_stats = self._get_season_stats(df, team_name)
                 source_label = f"Weighted ({venue})" if venue else "Weighted (All)"
                 
                 ratings = {
                    'attack': weighted_rating['attack'],
                    'defense': weighted_rating['defense'],
                    'creativity': season_stats.get('creativity_rating', 1.0),
                    'dominance': season_stats.get('dominance_rating', 1.0),
                    'expected_goals_avg': weighted_rating['expected_goals_avg'],
                    'source': source_label
                }

        # 2. Fallback
        if not ratings:
            stats = self._get_season_stats(df, team_name)
            ratings = {
                'attack': stats.get('attack_strength', 1.0),
                'defense': stats.get('defense_strength', 1.0),
                'creativity': stats.get('creativity_rating', 1.0),
                'dominance': stats.get('dominance_rating', 1.0),
                'expected_goals_avg': stats.get('expected_goals', 1.0),
                'source': 'Season Average'
            }
            
        # 3. Apply Player Tax (Modifier)
        if player_tax:
            # Tax < 1.0 means worse performance.
            # Attack * 0.9 = Lower Attack (Correct)
            # Defense * 0.9 = Lower Defense Rating = Better Defense? 
            # WAIT. Defense Rating 0.8 means "Concedes 0.8x League Avg". So LOWER is BETTER.
            # So if we have a Defense Tax (Team is worse), Defense Rating should INCREASE.
            # We should DIVIDE by tax? Or multiply by (2 - tax)?
            # Let's say Tax is relative strength. 0.9 means 90% strength.
            # Attack Strength * 0.9 (Weaker) -> Correct.
            # Defense Strength (Conceding Power). We want it to go UP (Concede More).
            # So Defense Strength / 0.9 -> Higher -> Weaker Defense. Correct.
            
            att_tax = player_tax.get('attack_tax', 1.0)
            def_tax = player_tax.get('defense_tax', 1.0)
            
            ratings['attack'] *= att_tax
            ratings['defense'] /= def_tax # Inverted for Defense
            
            ratings['source'] += " + PlayerImpact"
            
        return ratings

    def _get_season_stats(self, df, team_name):
        team_stats = df[df['team_name'] == team_name]
        if team_stats.empty:
            raise ValueError(f"Team '{team_name}' not found in data.")
        return team_stats.iloc[0]
