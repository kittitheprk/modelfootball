import os
import unicodedata

import pandas as pd

TEAM_ALIASES = {
    "Paris S-G": "Paris Saint-Germain",
    "PSG": "Paris Saint-Germain",
    "Rennes": "Stade Rennais",
    "Lyon": "Olympique Lyonnais",
    "Marseille": "Olympique de Marseille",
    "Monaco": "AS Monaco",
    "AS Monaco": "Monaco", # Fix for xG Engine linkage
    "Nice": "OGC Nice",
    "Lille": "LOSC Lille",
    "Brest": "Stade Brestois",
    "Stade Brestois": "Brest", 
    "Man Utd": "Manchester United",
    "Manchester Utd": "Manchester United",
    "Sheffield Utd": "Sheffield United",
    "Nott'm Forest": "Nottingham Forest",
    "Wolves": "Wolverhampton",
    "Brighton": "Brighton & Hove Albion",
    "Inter": "Internazionale",
    "Atletico Madrid": "Atletico Madrid",
    "Athletic Bilbao": "Athletic Club",
    "Real Betis": "Real Betis",
}

DEFAULT_ATTACK_XG = 1.30
DEFAULT_DEFENSE_XGA = 1.20
DEFAULT_FORM_LAST_5 = 7


def _safe_float(value, default=0.0):
    try:
        out = float(value)
        if pd.isna(out):
            return float(default)
        return out
    except Exception:
        return float(default)


def _clip(value, low, high):
    return max(low, min(high, float(value)))


class XGEngine:
    def __init__(self, league_name="Premier_League"):
        self.base_dir = f"Match Logs/{league_name}"
        self.aliases = TEAM_ALIASES

    @staticmethod
    def _normalize_text(text):
        raw = "" if text is None else str(text)
        norm = unicodedata.normalize("NFKD", raw)
        norm = "".join(ch for ch in norm if unicodedata.category(ch) != "Mn")
        return norm.lower().strip()

    def _candidate_team_names(self, team_name):
        out = []
        seen = set()
        original = str(team_name).strip()
        direct = self.aliases.get(original, original)

        reverse_aliases = [k for k, v in self.aliases.items() if v == original]
        for item in [original, direct] + reverse_aliases:
            key = self._normalize_text(item)
            if key and key not in seen:
                seen.add(key)
                out.append(item)

        expanded = []
        for item in out:
            expanded.append(item)
            expanded.append(item.replace(" Utd", " United"))
            expanded.append(item.replace(" United", " Utd"))

        final = []
        seen = set()
        for item in expanded:
            key = self._normalize_text(item)
            if key and key not in seen:
                seen.add(key)
                final.append(item)
        return final

    def _resolve_team_file(self, team_name):
        if not os.path.isdir(self.base_dir):
            return None

        for candidate in self._candidate_team_names(team_name):
            file_path = os.path.join(self.base_dir, f"{candidate}.xlsx")
            if os.path.exists(file_path):
                return file_path

        target = self._normalize_text(team_name)
        best_path = None
        best_score = -1
        for filename in os.listdir(self.base_dir):
            if not filename.lower().endswith(".xlsx"):
                continue
            stem = filename[:-5]
            stem_norm = self._normalize_text(stem)
            score = 0
            if stem_norm == target:
                score = 100
            elif target and (target in stem_norm or stem_norm in target):
                score = 40 + min(len(target), len(stem_norm))
            else:
                stem_tokens = set(stem_norm.split())
                target_tokens = set(target.split())
                score = len(stem_tokens.intersection(target_tokens)) * 6
            if score > best_score:
                best_score = score
                best_path = os.path.join(self.base_dir, filename)

        return best_path if best_score >= 6 else None

    @staticmethod
    def _find_col(df, exact=None, endswith=None, contains=None):
        if df is None or df.empty:
            return None

        exact = [x.lower() for x in (exact or [])]
        endswith = [x.lower() for x in (endswith or [])]
        contains = [x.lower() for x in (contains or [])]

        columns = list(df.columns)
        lowered = {str(col).lower(): col for col in columns}

        for key in exact:
            if key in lowered:
                return lowered[key]

        for col in columns:
            col_text = str(col).lower()
            if any(col_text.endswith(s) for s in endswith):
                return col

        for col in columns:
            col_text = str(col).lower()
            if any(s in col_text for s in contains):
                return col

        return None

    @staticmethod
    def _sort_recent(df, date_col):
        if df is None or df.empty:
            return df
        if not date_col or date_col not in df.columns:
            return df.copy()
        out = df.copy()
        out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
        out = out.sort_values(by=date_col, ascending=False, na_position="last")
        return out

    @staticmethod
    def _mean_numeric(series, default):
        if series is None:
            return float(default)
        vals = pd.to_numeric(series, errors="coerce").dropna()
        if vals.empty:
            return float(default)
        return float(vals.mean())

    def _compute_form(self, df_res):
        if df_res is None or df_res.empty:
            return DEFAULT_FORM_LAST_5, 0

        result_col = self._find_col(
            df_res,
            exact=["result"],
            endswith=["_result"],
            contains=["result"],
        )
        if not result_col:
            return DEFAULT_FORM_LAST_5, len(df_res)

        date_col = self._find_col(df_res, exact=["date"], endswith=["_date"])
        work = self._sort_recent(df_res, date_col)
        work = work[work[result_col].notna()].copy()
        if work.empty:
            return DEFAULT_FORM_LAST_5, 0

        points = 0
        for res in work.head(5)[result_col].astype(str):
            token = res.strip().upper()
            if token.startswith("W"):
                points += 3
            elif token.startswith("D"):
                points += 1
        return int(points), int(len(work))

    def _compute_attack_xg(self, df_shoot, n_games):
        if df_shoot is None or df_shoot.empty:
            return DEFAULT_ATTACK_XG, "default_attack"

        date_col = self._find_col(df_shoot, exact=["date"], endswith=["_date"])
        work = self._sort_recent(df_shoot, date_col).head(max(1, int(n_games)))

        xg_col = self._find_col(
            work,
            exact=["standard_xg", "expected_xg"],
            endswith=["_xg"],
            contains=["_xg", "expected_xg"],
        )
        if xg_col:
            xg_val = self._mean_numeric(work[xg_col], DEFAULT_ATTACK_XG)
            return _clip(xg_val, 0.25, 3.5), f"column:{xg_col}"

        shots_col = self._find_col(work, exact=["standard_sh"], endswith=["_sh"])
        sot_col = self._find_col(work, exact=["standard_sot"], endswith=["_sot"])
        goals_col = self._find_col(work, exact=["standard_gls"], endswith=["_gls"])
        gf_col = self._find_col(work, exact=["gf"], endswith=["_gf"])

        shots = pd.to_numeric(work[shots_col], errors="coerce") if shots_col else pd.Series(index=work.index, dtype=float)
        sot = pd.to_numeric(work[sot_col], errors="coerce") if sot_col else pd.Series(index=work.index, dtype=float)
        goals = pd.to_numeric(work[goals_col], errors="coerce") if goals_col else None
        if goals is None and gf_col:
            goals = pd.to_numeric(work[gf_col], errors="coerce")

        if shots_col or sot_col or goals is not None:
            if goals is None:
                goals = pd.Series(0.0, index=work.index)
            proxy = (shots.fillna(0.0) * 0.045) + (sot.fillna(0.0) * 0.080) + (goals.fillna(0.0) * 0.300)
            proxy_val = self._mean_numeric(proxy, DEFAULT_ATTACK_XG)
            return _clip(proxy_val, 0.35, 3.2), "proxy:shots_sot_goals"

        return DEFAULT_ATTACK_XG, "default_attack"

    def _compute_defense_xga(self, df_goalkeeping, df_res, n_games):
        if df_goalkeeping is not None and not df_goalkeeping.empty:
            date_col = self._find_col(df_goalkeeping, exact=["date"], endswith=["_date"])
            work = self._sort_recent(df_goalkeeping, date_col).head(max(1, int(n_games)))

            psxg_col = self._find_col(
                work,
                exact=["performance_psxg"],
                endswith=["_psxg"],
                contains=["psxg"],
            )
            if psxg_col:
                xga_val = self._mean_numeric(work[psxg_col], DEFAULT_DEFENSE_XGA)
                return _clip(xga_val, 0.20, 3.5), f"column:{psxg_col}"

            ga_col = self._find_col(work, exact=["performance_ga", "ga"], endswith=["_ga"])
            sota_col = self._find_col(work, exact=["performance_sota"], endswith=["_sota"])
            save_col = self._find_col(
                work,
                exact=["performance_save%"],
                endswith=["_save%"],
                contains=["save%"],
            )

            if ga_col or sota_col:
                ga = pd.to_numeric(work[ga_col], errors="coerce") if ga_col else pd.Series(0.0, index=work.index)
                sota = pd.to_numeric(work[sota_col], errors="coerce") if sota_col else pd.Series(0.0, index=work.index)

                if save_col:
                    save_pct = pd.to_numeric(work[save_col], errors="coerce")
                    save_ratio = save_pct.where(save_pct <= 1.0, save_pct / 100.0).clip(lower=0.0, upper=1.0)
                else:
                    save_ratio = pd.Series(0.70, index=work.index)

                shot_quality = (1.0 - save_ratio.fillna(0.70)) * 0.90
                proxy = (ga.fillna(0.0) * 0.62) + (sota.fillna(0.0) * 0.06) + shot_quality
                proxy_val = self._mean_numeric(proxy, DEFAULT_DEFENSE_XGA)
                return _clip(proxy_val, 0.30, 3.2), "proxy:ga_sota_save"

        if df_res is not None and not df_res.empty:
            date_col = self._find_col(df_res, exact=["date"], endswith=["_date"])
            work = self._sort_recent(df_res, date_col).head(max(1, int(n_games)))
            ga_col = self._find_col(work, exact=["ga"], endswith=["_ga"])
            if ga_col:
                ga_val = self._mean_numeric(work[ga_col], DEFAULT_DEFENSE_XGA)
                return _clip(ga_val, 0.30, 3.2), f"column:{ga_col}"

        return DEFAULT_DEFENSE_XGA, "default_defense"

    def get_team_rolling_stats(self, team_name, n_games=10):
        """
        Calculates rolling xG/xGA and Form (Last 5 games).
        Supports both legacy and prefixed match-log schemas.
        """
        team_file = self._resolve_team_file(team_name)

        if not team_file:
            print(f"[XGEngine] Warning: Match logs not found for {team_name} in {self.base_dir}")
            return None

        try:
            df_shoot = None
            df_goalkeeping = None
            df_res = None

            try:
                df_shoot = pd.read_excel(team_file, sheet_name="Shooting")
            except Exception:
                df_shoot = None

            try:
                df_goalkeeping = pd.read_excel(team_file, sheet_name="Goalkeeping")
            except Exception:
                df_goalkeeping = None

            if df_shoot is not None and not df_shoot.empty:
                df_res = df_shoot
            else:
                try:
                    df_res = pd.read_excel(team_file, sheet_name=0)
                except Exception:
                    df_res = None

            form_score, games_played = self._compute_form(df_res)
            avg_xg_for, xg_source = self._compute_attack_xg(df_shoot if df_shoot is not None else df_res, n_games=n_games)
            avg_xga, xga_source = self._compute_defense_xga(df_goalkeeping, df_res, n_games=n_games)

            return {
                "team": team_name,
                "file_used": os.path.basename(team_file),
                "games_played": int(games_played),
                "form_last_5": int(form_score),  # 0-15
                "attack": {
                    "xg_per_game": float(avg_xg_for),
                },
                "defense": {
                    "xga_per_game": float(avg_xga),
                },
                "xg_source": xg_source,
                "xga_source": xga_source,
            }
        except Exception as e:
            print(f"[XGEngine] Error processing {team_name}: {e}")
            return None

if __name__ == "__main__":
    # Test
    engine = XGEngine()
    stats = engine.get_team_rolling_stats("Sunderland", n_games=5)
    print(stats)
