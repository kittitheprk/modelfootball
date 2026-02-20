import json
import math
import os
import re
import unicodedata
from datetime import timedelta

import numpy as np

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

TEAM_NAME_ALIASES = {
    "paris s g": "Paris Saint-Germain",
    "psg": "Paris Saint-Germain",
    "stade rennais": "Rennes",
    "olympique lyonnais": "Lyon",
    "olympique de marseille": "Marseille",
    "as monaco": "Monaco",
    "ogc nice": "Nice",
    "losc lille": "Lille",
    "stade brestois": "Brest",
    "rc lens": "Lens",
    "rc strasbourg": "Strasbourg",
    "racing club de lens": "Lens",
    "racing club de strasbourg": "Strasbourg",
    "man utd": "Manchester United",
    "manchester utd": "Manchester United",
    "sheffield utd": "Sheffield United",
    "nott m forest": "Nottingham Forest",
    "wolves": "Wolverhampton",
    "brighton": "Brighton & Hove Albion",
    "girona": "Girona FC",
    "alaves": "Deportivo Alaves",
    "atletico madrid": "Atletico Madrid",
    "athletic": "Athletic Club",
    "inter": "Internazionale",
    "man city": "Manchester City",
    "newcastle": "Newcastle United",
    "spurs": "Tottenham Hotspur",
}

_CHAR_CACHE = {}
CALIBRATION_PATH = "model_calibration.json"


def _safe_float(value, default=0.0):
    try:
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return float(default)
        return out
    except Exception:
        return float(default)


def _clip(value, low, high):
    return max(low, min(high, value))


def _tanh_norm(value, scale):
    return math.tanh(max(0.0, float(value)) / max(1e-9, float(scale)))


def _norm_text(text):
    text = "" if text is None else str(text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^0-9a-zA-Z\s]", " ", text).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _canonical_team_name(team_name):
    normalized = _norm_text(team_name)
    mapped = TEAM_NAME_ALIASES.get(normalized)
    return mapped if mapped else team_name


def _token_overlap_score(a, b):
    a_tokens = set(_norm_text(a).split())
    b_tokens = set(_norm_text(b).split())
    if not a_tokens or not b_tokens:
        return 0
    return len(a_tokens.intersection(b_tokens))


def _find_file_by_team(base_dir, league, team_name, suffix):
    league_dir = os.path.join(base_dir, league)
    if not os.path.isdir(league_dir):
        return None

    candidates = []
    canonical = _canonical_team_name(team_name)
    if canonical != team_name:
        candidates.append(canonical)
    candidates.append(team_name)

    for c in candidates:
        direct = os.path.join(league_dir, f"{c}_{suffix}.xlsx")
        if os.path.exists(direct):
            return direct

    target_norm = _norm_text(team_name)
    best_path = None
    best_score = -1

    for fname in os.listdir(league_dir):
        if not fname.lower().endswith(f"_{suffix}.xlsx"):
            continue
        team_part = fname[: -(len(f"_{suffix}.xlsx"))]
        team_norm = _norm_text(team_part)

        score = 0
        if team_norm == target_norm:
            score = 100
        elif target_norm and (target_norm in team_norm or team_norm in target_norm):
            score = 40 + min(len(target_norm), len(team_norm))
        else:
            score = _token_overlap_score(target_norm, team_norm) * 6

        if score > best_score:
            best_score = score
            best_path = os.path.join(league_dir, fname)

    return best_path if best_score >= 6 else None


def _find_match_log_file(league, team_name):
    logs_dir = os.path.join("Match Logs", league)
    if not os.path.isdir(logs_dir):
        return None

    candidates = []
    canonical = _canonical_team_name(team_name)
    if canonical != team_name:
        candidates.append(canonical)
    candidates.append(team_name)

    for c in candidates:
        direct = os.path.join(logs_dir, f"{c}.xlsx")
        if os.path.exists(direct):
            return direct

    target_norm = _norm_text(team_name)
    best_path = None
    best_score = -1

    for fname in os.listdir(logs_dir):
        if not fname.lower().endswith(".xlsx"):
            continue
        stem = fname[:-5]
        stem_norm = _norm_text(stem)

        score = 0
        if stem_norm == target_norm:
            score = 100
        elif target_norm and (target_norm in stem_norm or stem_norm in target_norm):
            score = 40 + min(len(target_norm), len(stem_norm))
        else:
            score = _token_overlap_score(target_norm, stem_norm) * 6

        if score > best_score:
            best_score = score
            best_path = os.path.join(logs_dir, fname)

    return best_path if best_score >= 6 else None


def _poisson_pmf(k, lam):
    if k < 0:
        return 0.0
    lam = max(1e-9, float(lam))
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _build_score_matrix(lambda_home, lambda_away, max_goals=10, rho=-0.07):
    home_probs = np.array([_poisson_pmf(i, lambda_home) for i in range(max_goals + 1)])
    away_probs = np.array([_poisson_pmf(i, lambda_away) for i in range(max_goals + 1)])
    mat = np.outer(home_probs, away_probs)

    if max_goals >= 1:
        tau00 = max(0.01, 1 - rho * lambda_home * lambda_away)
        tau01 = max(0.01, 1 + rho * lambda_home)
        tau10 = max(0.01, 1 + rho * lambda_away)
        tau11 = max(0.01, 1 - rho)
        mat[0, 0] *= tau00
        mat[0, 1] *= tau01
        mat[1, 0] *= tau10
        mat[1, 1] *= tau11

    total = mat.sum()
    if total > 0:
        mat = mat / total
    return mat


def _top_scores(prob_matrix, top_n=3):
    flat = []
    h_size, a_size = prob_matrix.shape
    for h in range(h_size):
        for a in range(a_size):
            flat.append((h, a, prob_matrix[h, a]))
    flat.sort(key=lambda x: x[2], reverse=True)
    return flat[:top_n]


def _load_model_calibration(path=CALIBRATION_PATH):
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _team_calibration_entry(by_team, team_name):
    if not by_team or not team_name:
        return None

    direct = by_team.get(team_name)
    if isinstance(direct, dict):
        return direct

    canonical = _canonical_team_name(team_name)
    if canonical != team_name:
        direct = by_team.get(canonical)
        if isinstance(direct, dict):
            return direct

    target = _norm_text(team_name)
    for key, value in by_team.items():
        if _norm_text(key) == target and isinstance(value, dict):
            return value
    return None


def _blend_scale(raw_scale, reliability):
    base = _safe_float(raw_scale, 1.0)
    rel = _clip(_safe_float(reliability, 0.0), 0.0, 1.0)
    return 1.0 + ((base - 1.0) * rel)


def _apply_model_calibration(lambda_home, lambda_away, calibration, league, home_team, away_team):
    ctx = {
        "enabled": False,
        "path": CALIBRATION_PATH,
        "home_multiplier": 1.0,
        "away_multiplier": 1.0,
        "global_home_scale": 1.0,
        "global_away_scale": 1.0,
        "league_home_scale": 1.0,
        "league_away_scale": 1.0,
    }
    if not calibration or not isinstance(calibration, dict):
        return lambda_home, lambda_away, ctx

    g = calibration.get("global", {}) if isinstance(calibration.get("global"), dict) else {}
    global_home_scale = _blend_scale(g.get("home_scale"), g.get("reliability", 1.0))
    global_away_scale = _blend_scale(g.get("away_scale"), g.get("reliability", 1.0))
    ctx["global_home_scale"] = global_home_scale
    ctx["global_away_scale"] = global_away_scale

    league_map = calibration.get("by_league", {}) if isinstance(calibration.get("by_league"), dict) else {}
    league_row = league_map.get(league) if league else None
    if not isinstance(league_row, dict) and league:
        target = _norm_text(league.replace("_", " "))
        for key, val in league_map.items():
            if _norm_text(str(key).replace("_", " ")) == target and isinstance(val, dict):
                league_row = val
                break
    if not isinstance(league_row, dict):
        league_row = {}
    league_home_scale = _blend_scale(league_row.get("home_scale"), league_row.get("reliability", 1.0))
    league_away_scale = _blend_scale(league_row.get("away_scale"), league_row.get("reliability", 1.0))
    ctx["league_home_scale"] = league_home_scale
    ctx["league_away_scale"] = league_away_scale

    home_multiplier = global_home_scale * league_home_scale
    away_multiplier = global_away_scale * league_away_scale

    by_team = calibration.get("by_team", {}) if isinstance(calibration.get("by_team"), dict) else {}
    h_team = _team_calibration_entry(by_team, home_team)
    a_team = _team_calibration_entry(by_team, away_team)

    if isinstance(h_team, dict) and isinstance(a_team, dict):
        h_attack = _blend_scale(h_team.get("attack_scale"), h_team.get("reliability"))
        h_defense = _blend_scale(h_team.get("defense_scale"), h_team.get("reliability"))
        a_attack = _blend_scale(a_team.get("attack_scale"), a_team.get("reliability"))
        a_defense = _blend_scale(a_team.get("defense_scale"), a_team.get("reliability"))

        home_multiplier *= h_attack * a_defense
        away_multiplier *= a_attack * h_defense

        ctx["home_team_attack_scale"] = h_attack
        ctx["home_team_defense_scale"] = h_defense
        ctx["away_team_attack_scale"] = a_attack
        ctx["away_team_defense_scale"] = a_defense

    home_multiplier = _clip(home_multiplier, 0.90, 1.12)
    away_multiplier = _clip(away_multiplier, 0.90, 1.12)
    ctx["enabled"] = True
    ctx["home_multiplier"] = float(home_multiplier)
    ctx["away_multiplier"] = float(away_multiplier)

    return lambda_home * home_multiplier, lambda_away * away_multiplier, ctx


def _clean_player_name(name):
    if name is None:
        return ""
    text = str(name).replace("*", " ").replace("•", " ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -,:;")
    return text


def _split_player_list(raw_text):
    parts = re.split(r",|/|;|\band\b", raw_text, flags=re.IGNORECASE)
    out = []
    for part in parts:
        cleaned = _clean_player_name(part)
        if cleaned:
            out.append(cleaned)
    return out


def _heading_matches_team(heading, team_name):
    heading_norm = _norm_text(heading)
    team_norm = _norm_text(team_name)
    if not heading_norm or not team_norm:
        return False
    if team_norm in heading_norm or heading_norm in team_norm:
        return True
    return _token_overlap_score(heading_norm, team_norm) >= 2


def _parse_confirmed_lineups(context_text, home_team, away_team):
    out = {"home": [], "away": []}
    if not context_text:
        return out

    active = None
    in_lineup_block = False

    for raw_line in str(context_text).splitlines():
        line = raw_line.strip()
        if not line:
            continue

        norm_line = _norm_text(line)
        if "confirmed lineup" in norm_line or "confirmed lineups" in norm_line:
            in_lineup_block = True
            continue

        if "team news" in norm_line or "context" in norm_line:
            active = None
            if "team news" in norm_line:
                in_lineup_block = False
            continue

        if line.startswith("**") and line.endswith("**"):
            heading = line.strip("* ")
            heading = heading.split(":")[0]
            heading = re.sub(r"\([^)]*\)", "", heading).strip()

            if _heading_matches_team(heading, home_team):
                active = "home"
                continue
            if _heading_matches_team(heading, away_team):
                active = "away"
                continue

            if in_lineup_block:
                active = None

        if not active:
            continue

        role_line = re.match(r"^[\-\*]?\s*\*\*[^*]+:\*\*\s*(.+)$", line)
        if role_line:
            for p in _split_player_list(role_line.group(1)):
                if p not in out[active]:
                    out[active].append(p)
            continue

        if line.startswith("*") or line.startswith("-"):
            bullet_text = _clean_player_name(line.lstrip("*- ").strip())
            if bullet_text and len(bullet_text.split()) >= 1 and "missing" not in _norm_text(bullet_text):
                if bullet_text not in out[active]:
                    out[active].append(bullet_text)

    out["home"] = out["home"][:11]
    out["away"] = out["away"][:11]
    return out


def _load_characteristics_lookup(league):
    if pd is None:
        return {}
    if league in _CHAR_CACHE:
        return _CHAR_CACHE[league]

    path = os.path.join("player_characteristics", f"{league}_Characteristics.xlsx")
    if not os.path.exists(path):
        _CHAR_CACHE[league] = {}
        return {}

    try:
        df = pd.read_excel(path)
    except Exception:
        _CHAR_CACHE[league] = {}
        return {}

    if df.empty or "Player" not in df.columns:
        _CHAR_CACHE[league] = {}
        return {}

    out = {}
    for _, row in df.iterrows():
        raw_name = str(row.get("Player", ""))
        # Some files prefix ranking digits before names, e.g., "1Christantus Uche"
        cleaned_name = re.sub(r"^\d+", "", raw_name).strip()
        key = _norm_text(cleaned_name)
        if not key:
            continue
        out[key] = {
            "strengths": str(row.get("Strengths", "") or ""),
            "weaknesses": str(row.get("Weaknesses", "") or ""),
        }

    _CHAR_CACHE[league] = out
    return out


def _load_team_player_frame(league, team_name):
    if pd is None:
        return None

    stats_file = _find_file_by_team("sofaplayer", league, team_name, "stats")
    if not stats_file:
        return None

    try:
        df = pd.read_excel(stats_file)
    except Exception:
        return None

    if df.empty:
        return None

    if "Player_Name" not in df.columns and "Name" in df.columns:
        df = df.rename(columns={"Name": "Player_Name"})
    if "Player_ID" not in df.columns and "ID" in df.columns:
        df = df.rename(columns={"ID": "Player_ID"})
    if "Player_Name" not in df.columns:
        return None

    df = df.copy()
    df["__name_key"] = df["Player_Name"].map(_norm_text)

    char_lookup = _load_characteristics_lookup(league)
    if char_lookup:
        df["Strengths_Text"] = df["__name_key"].map(lambda k: char_lookup.get(k, {}).get("strengths", ""))
        df["Weaknesses_Text"] = df["__name_key"].map(lambda k: char_lookup.get(k, {}).get("weaknesses", ""))
    else:
        df["Strengths_Text"] = ""
        df["Weaknesses_Text"] = ""

    pos_file = _find_file_by_team("position", league, team_name, "positions")
    if pos_file:
        try:
            pos_df = pd.read_excel(pos_file)
        except Exception:
            pos_df = None

        if pos_df is not None and not pos_df.empty:
            pos_df = pos_df.copy()
            if "Name" not in pos_df.columns and "Player_Name" in pos_df.columns:
                pos_df = pos_df.rename(columns={"Player_Name": "Name"})
            if "ID" not in pos_df.columns and "Player_ID" in pos_df.columns:
                pos_df = pos_df.rename(columns={"Player_ID": "ID"})
            if "Name" in pos_df.columns:
                pos_df["__name_key"] = pos_df["Name"].map(_norm_text)

            pos_cols = [c for c in [
                "ID",
                "__name_key",
                "Primary_Position",
                "Secondary_Positions",
                "Detailed_Positions_All",
                "Position_General",
            ] if c in pos_df.columns]
            pos_df = pos_df[pos_cols].drop_duplicates()

            if "ID" in pos_df.columns and "Player_ID" in df.columns:
                df = df.merge(
                    pos_df.drop_duplicates(subset=["ID"]),
                    left_on="Player_ID",
                    right_on="ID",
                    how="left",
                    suffixes=("", "_pos"),
                )
            elif "__name_key" in pos_df.columns:
                df = df.merge(
                    pos_df.drop_duplicates(subset=["__name_key"]),
                    on="__name_key",
                    how="left",
                    suffixes=("", "_pos"),
                )

            if "Primary_Position" not in df.columns:
                df["Primary_Position"] = np.nan
            if "__name_key" in pos_df.columns and "Primary_Position" in pos_df.columns:
                lookup = (
                    pos_df.dropna(subset=["__name_key"])
                    .drop_duplicates(subset=["__name_key"])
                    .set_index("__name_key")["Primary_Position"]
                )
                df["Primary_Position"] = df["Primary_Position"].where(
                    df["Primary_Position"].notna(),
                    df["__name_key"].map(lookup),
                )

    if "Primary_Position" not in df.columns:
        df["Primary_Position"] = np.nan

    return df


def _role_from_position(pos_value):
    pos = str(pos_value or "").upper().strip()
    if not pos:
        return "MID"
    if pos in {"GK"}:
        return "GK"
    if pos in {"CB", "LB", "RB", "LWB", "RWB", "WB"}:
        return "DEF"
    if pos in {"DM", "CDM", "CM", "CAM", "AM", "LM", "RM"}:
        return "MID"
    if pos in {"ST", "CF", "LW", "RW", "LF", "RF", "FW"}:
        return "ATT"
    if pos.startswith("D"):
        return "DEF"
    if pos.startswith("M"):
        return "MID"
    if pos.startswith("F"):
        return "ATT"
    return "MID"


def _lineup_priority(row):
    starts = _safe_float(row.get("matchesStarted"), 0.0)
    apps = _safe_float(row.get("appearances"), 0.0)
    mins = _safe_float(row.get("minutesPlayed"), 0.0)
    rating = _safe_float(row.get("rating"), 6.6)
    return (starts * 4.0) + (apps * 1.5) + (mins / 90.0) + (rating * 1.3)


def _project_lineup(df):
    if df is None or df.empty:
        return df

    df = df.copy()
    df["__role"] = df["Primary_Position"].map(_role_from_position)
    df["__priority"] = df.apply(_lineup_priority, axis=1)

    selected = []
    selected_set = set()

    def pick(role, count):
        subset = df[df["__role"] == role].sort_values(by="__priority", ascending=False)
        for idx in subset.index:
            if idx in selected_set:
                continue
            selected.append(idx)
            selected_set.add(idx)
            if len([x for x in selected if x in subset.index]) >= count:
                break

    pick("GK", 1)
    pick("DEF", 4)
    pick("MID", 3)
    pick("ATT", 3)

    if len(selected) < 11:
        for idx in df.sort_values(by="__priority", ascending=False).index:
            if idx not in selected_set:
                selected.append(idx)
                selected_set.add(idx)
            if len(selected) >= 11:
                break

    return df.loc[selected[:11]].copy()


def _match_player_row(df, lineup_name, used_indexes):
    target = _norm_text(lineup_name)
    if not target:
        return None

    exact = df[(df["__name_key"] == target) & (~df.index.isin(used_indexes))]
    if not exact.empty:
        return exact.sort_values(by="__priority", ascending=False).index[0]

    tokens = [t for t in target.split() if len(t) >= 3]
    best_idx = None
    best_score = 0
    best_priority = -1e9

    for idx, row in df.iterrows():
        if idx in used_indexes:
            continue
        candidate = row.get("__name_key", "")
        if not candidate:
            continue

        score = 0
        if target in candidate or candidate in target:
            score += 20
        for token in tokens:
            if token in candidate:
                score += len(token)
        if tokens and candidate.endswith(tokens[-1]):
            score += 8

        if score > 0:
            pr = _safe_float(row.get("__priority"), 0.0)
            if score > best_score or (score == best_score and pr > best_priority):
                best_score = score
                best_priority = pr
                best_idx = idx

    return best_idx if best_score >= 6 else None


def _lineup_from_names(df, lineup_names, projected_lineup):
    if not lineup_names:
        return projected_lineup, 0

    used = set()
    selected = []

    for name in lineup_names:
        idx = _match_player_row(df, name, used)
        if idx is not None:
            selected.append(idx)
            used.add(idx)

    matched = len(selected)
    if matched == 0:
        return projected_lineup, 0

    for idx in projected_lineup.index:
        if idx not in used:
            selected.append(idx)
            used.add(idx)
        if len(selected) >= 11:
            break

    if len(selected) < 11:
        for idx in df.sort_values(by="__priority", ascending=False).index:
            if idx not in used:
                selected.append(idx)
                used.add(idx)
            if len(selected) >= 11:
                break

    return df.loc[selected[:11]].copy(), matched


def _per90(row, field, minutes):
    return (_safe_float(row.get(field), 0.0) / max(1.0, minutes)) * 90.0


def _player_profile(row):
    minutes = _safe_float(row.get("minutesPlayed"), 0.0)
    apps = max(1.0, _safe_float(row.get("appearances"), 1.0))
    if minutes <= 0:
        minutes = apps * 60.0

    rating = _safe_float(row.get("rating"), 6.7)
    rating_norm = _clip((rating - 5.8) / 2.4, 0.0, 1.35)

    xg_p90 = _per90(row, "expectedGoals", minutes)
    goals_p90 = _per90(row, "goals", minutes)
    xa_p90 = _per90(row, "expectedAssists", minutes)
    assists_p90 = _per90(row, "assists", minutes)
    key_pass_p90 = _per90(row, "keyPasses", minutes)
    dribble_p90 = _per90(row, "successfulDribbles", minutes)
    shots_on_target_p90 = _per90(row, "shotsOnTarget", minutes)
    opp_half_passes_p90 = _per90(row, "accurateOppositionHalfPasses", minutes)
    big_created_p90 = _per90(row, "bigChancesCreated", minutes)
    inside_box_shots_p90 = _per90(row, "shotsFromInsideTheBox", minutes)

    tackles_p90 = _per90(row, "tackles", minutes)
    interceptions_p90 = _per90(row, "interceptions", minutes)
    clearances_p90 = _per90(row, "clearances", minutes)
    duel_pct = _safe_float(row.get("totalDuelsWonPercentage"), 50.0)
    aerial_pct = _safe_float(row.get("aerialDuelsWonPercentage"), duel_pct)

    finisher_signal = _tanh_norm((xg_p90 * 0.7) + (goals_p90 * 0.55) + (shots_on_target_p90 * 0.22), 0.85)
    creator_signal = _tanh_norm((xa_p90 * 0.9) + (assists_p90 * 0.55) + (key_pass_p90 * 0.18) + (dribble_p90 * 0.08), 0.75)
    attack = (0.50 * rating_norm) + (0.30 * finisher_signal) + (0.20 * creator_signal)
    xt_proxy = _clip(
        (0.42 * _tanh_norm((xa_p90 * 1.7) + (key_pass_p90 * 0.75) + (big_created_p90 * 0.55), 2.1))
        + (0.30 * _tanh_norm((dribble_p90 * 0.8) + (opp_half_passes_p90 / 35.0), 1.7))
        + (0.28 * _tanh_norm((xg_p90 * 1.2) + (inside_box_shots_p90 * 0.24), 1.35)),
        0.0,
        1.2,
    )

    defensive_actions = _tanh_norm((tackles_p90 * 0.45) + (interceptions_p90 * 0.55) + (clearances_p90 * 0.25), 1.25)
    duel_signal = _clip(((duel_pct / 100.0) + (aerial_pct / 100.0)) * 0.5, 0.0, 1.2)
    defense = (0.52 * rating_norm) + (0.30 * defensive_actions) + (0.18 * duel_signal)
    control = _clip(
        (0.44 * _tanh_norm((key_pass_p90 * 0.55) + (xa_p90 * 1.6), 1.4))
        + (0.30 * _tanh_norm(dribble_p90, 2.4))
        + (0.26 * _clip(duel_pct / 100.0, 0.0, 1.15)),
        0.0,
        1.2,
    )

    strengths = _norm_text(row.get("Strengths_Text", ""))
    weaknesses = _norm_text(row.get("Weaknesses_Text", ""))

    attack_trait_adj = 0.0
    defense_trait_adj = 0.0

    if "finishing" in strengths:
        attack_trait_adj += 0.03
    if "key passes" in strengths or "through balls" in strengths:
        attack_trait_adj += 0.03
    if "dribbling" in strengths:
        attack_trait_adj += 0.02
    if "aerial duels" in strengths:
        attack_trait_adj += 0.01
        defense_trait_adj += 0.02
    if "tackling" in strengths or "ball interception" in strengths or "defensive contribution" in strengths:
        defense_trait_adj += 0.03
    if "concentration" in strengths:
        defense_trait_adj += 0.02

    if "finishing" in weaknesses:
        attack_trait_adj -= 0.03
    if "passing" in weaknesses:
        attack_trait_adj -= 0.02
    if "dribbling" in weaknesses or "holding on to the ball" in weaknesses:
        attack_trait_adj -= 0.02
    if "aerial duels" in weaknesses:
        attack_trait_adj -= 0.01
        defense_trait_adj -= 0.02
    if "tackling" in weaknesses or "defensive contribution" in weaknesses:
        defense_trait_adj -= 0.03
    if "discipline" in weaknesses:
        defense_trait_adj -= 0.01

    attack += _clip(attack_trait_adj, -0.06, 0.08)
    defense += _clip(defense_trait_adj, -0.06, 0.08)

    role = _role_from_position(row.get("Primary_Position"))
    if role == "ATT":
        attack *= 1.14
        defense *= 0.76
    elif role == "MID":
        pass
    elif role == "DEF":
        attack *= 0.72
        defense *= 1.22
    elif role == "GK":
        attack *= 0.28
        defense *= 1.36

    reliability = _clip(minutes / 900.0, 0.25, 1.0)
    fallback_level = 0.45 + (0.20 * rating_norm)
    attack = (attack * reliability) + (fallback_level * (1.0 - reliability))
    defense = (defense * reliability) + (fallback_level * (1.0 - reliability))
    control = (control * reliability) + ((fallback_level * 0.95) * (1.0 - reliability))

    return {
        "name": row.get("Player_Name", "Unknown"),
        "primary_position": str(row.get("Primary_Position", "") or "").upper().strip(),
        "role": role,
        "attack": float(attack),
        "defense": float(defense),
        "control": float(control),
        "minutes": float(minutes),
        "workload": _clip(minutes / (apps * 90.0), 0.40, 1.20),
        "xg_p90": float(xg_p90),
        "xa_p90": float(xa_p90),
        "xt_proxy": float(xt_proxy),
        "aerial_pct": float(aerial_pct),
        "key_passes_p90": float(key_pass_p90),
        "dribbles_p90": float(dribble_p90),
        "tackles_p90": float(tackles_p90),
    }


def _aggregate_lineup(lineup_df):
    if lineup_df is None or lineup_df.empty:
        return {
            "attack": 0.70,
            "defense": 0.70,
            "overall": 0.70,
            "load_index": 0.90,
            "xg_p90": 0.0,
            "xa_p90": 0.0,
            "xt_proxy": 0.0,
            "players": [],
        }

    attack_weights = {"GK": 0.35, "DEF": 0.72, "MID": 1.00, "ATT": 1.30}
    defense_weights = {"GK": 1.45, "DEF": 1.26, "MID": 1.00, "ATT": 0.55}
    overall_weights = {"GK": 0.90, "DEF": 1.00, "MID": 1.00, "ATT": 1.10}

    players = []
    att_sum = att_w_sum = 0.0
    def_sum = def_w_sum = 0.0
    ov_sum = ov_w_sum = 0.0
    xg_sum = xa_sum = xt_sum = 0.0
    workloads = []

    for _, row in lineup_df.iterrows():
        p = _player_profile(row)
        players.append(p)

        rel = _clip(p["minutes"] / 900.0, 0.40, 1.00)
        aw = attack_weights[p["role"]] * rel
        dw = defense_weights[p["role"]] * rel
        ow = overall_weights[p["role"]] * rel

        att_sum += p["attack"] * aw
        att_w_sum += aw
        def_sum += p["defense"] * dw
        def_w_sum += dw
        ov_sum += ((p["attack"] + p["defense"]) * 0.5) * ow
        ov_w_sum += ow
        xg_sum += p["xg_p90"] * aw
        xa_sum += p["xa_p90"] * aw
        xt_sum += p["xt_proxy"] * ow
        workloads.append(p["workload"])

    return {
        "attack": float(att_sum / max(1e-9, att_w_sum)),
        "defense": float(def_sum / max(1e-9, def_w_sum)),
        "overall": float(ov_sum / max(1e-9, ov_w_sum)),
        "load_index": float(np.mean(workloads) if workloads else 0.90),
        "xg_p90": float(xg_sum / max(1e-9, att_w_sum)),
        "xa_p90": float(xa_sum / max(1e-9, att_w_sum)),
        "xt_proxy": float(xt_sum / max(1e-9, ov_w_sum)),
        "players": players,
    }


def _build_team_profile(df, lineup_names):
    if df is None or df.empty:
        return None

    work = df.copy()
    work["__priority"] = work.apply(_lineup_priority, axis=1)
    if "__name_key" not in work.columns:
        work["__name_key"] = work["Player_Name"].map(_norm_text)

    projected = _project_lineup(work)
    actual, matched_count = _lineup_from_names(work, lineup_names, projected)

    projected_stats = _aggregate_lineup(projected)
    actual_stats = _aggregate_lineup(actual)

    if lineup_names and matched_count >= 8:
        source = "confirmed"
    elif lineup_names and matched_count > 0:
        source = "hybrid"
    else:
        source = "projected"

    confidence = _clip(matched_count / 11.0, 0.0, 1.0) if lineup_names else 0.0
    attack_delta = 0.0
    defense_delta = 0.0
    if source in {"confirmed", "hybrid"}:
        attack_delta = ((actual_stats["attack"] / max(1e-9, projected_stats["attack"])) - 1.0) * confidence
        defense_delta = ((actual_stats["defense"] / max(1e-9, projected_stats["defense"])) - 1.0) * confidence

    return {
        "source": source,
        "lineup_size": int(len(actual)),
        "matched_count": int(matched_count),
        "actual": actual_stats,
        "projected": projected_stats,
        "attack_delta": float(_clip(attack_delta, -0.20, 0.15)),
        "defense_delta": float(_clip(defense_delta, -0.20, 0.15)),
    }


def _pick_best_player(players, position_pool=None, metric="attack", fallback_role=None):
    if not players:
        return None

    subset = []
    if position_pool:
        pool = {p.upper() for p in position_pool}
        subset = [x for x in players if x.get("primary_position", "").upper() in pool]
    if not subset and fallback_role:
        subset = [x for x in players if x.get("role") == fallback_role]
    if not subset:
        subset = players

    return max(subset, key=lambda x: _safe_float(x.get(metric), 0.0))


def _duel_score(attacker, defender, central=False):
    if attacker is None or defender is None:
        return 0.0
    score = _safe_float(attacker.get("attack"), 0.0) - _safe_float(defender.get("defense"), 0.0)
    if central:
        score += ((_safe_float(attacker.get("aerial_pct"), 50.0) - _safe_float(defender.get("aerial_pct"), 50.0)) / 100.0) * 0.28
    return _clip(score, -1.2, 1.2)


def _midfield_duel_score(playmaker, stopper):
    if playmaker is None or stopper is None:
        return 0.0
    score = (
        (0.62 * _safe_float(playmaker.get("control"), 0.0))
        + (0.24 * _safe_float(playmaker.get("xa_p90"), 0.0))
        - (0.60 * _safe_float(stopper.get("defense"), 0.0))
        - (0.20 * _safe_float(stopper.get("control"), 0.0))
    )
    return _clip(score, -1.2, 1.2)


def _duel_edge(score, perspective="home", tolerance=0.08):
    if score > tolerance:
        return perspective
    if score < -tolerance:
        return "away" if perspective == "home" else "home"
    return "even"


def _derive_matchups(home_profile, away_profile):
    if not home_profile or not away_profile:
        return {
            "home_adj": 0.0,
            "away_adj": 0.0,
            "highlights": [],
            "position_battles": [],
        }

    hp = home_profile["actual"]["players"]
    ap = away_profile["actual"]["players"]

    home_lw = _pick_best_player(hp, {"LW", "LM", "LWB"}, "attack", fallback_role="ATT")
    home_rw_pool = [p for p in hp if p is not home_lw]
    home_rw = _pick_best_player(home_rw_pool, {"RW", "RM", "RWB"}, "attack", fallback_role="ATT") or home_lw
    home_st_pool = [p for p in hp if p is not home_lw and p is not home_rw]
    home_st = _pick_best_player(home_st_pool, {"ST", "CF", "FW"}, "attack", fallback_role="ATT") or home_rw

    away_lw = _pick_best_player(ap, {"LW", "LM", "LWB"}, "attack", fallback_role="ATT")
    away_rw_pool = [p for p in ap if p is not away_lw]
    away_rw = _pick_best_player(away_rw_pool, {"RW", "RM", "RWB"}, "attack", fallback_role="ATT") or away_lw
    away_st_pool = [p for p in ap if p is not away_lw and p is not away_rw]
    away_st = _pick_best_player(away_st_pool, {"ST", "CF", "FW"}, "attack", fallback_role="ATT") or away_rw

    home_lb = _pick_best_player(hp, {"LB", "LWB"}, "defense", fallback_role="DEF")
    home_rb_pool = [p for p in hp if p is not home_lb]
    home_rb = _pick_best_player(home_rb_pool, {"RB", "RWB"}, "defense", fallback_role="DEF") or home_lb
    home_cb_pool = [p for p in hp if p is not home_lb and p is not home_rb]
    home_cb = _pick_best_player(home_cb_pool, {"CB"}, "defense", fallback_role="DEF") or home_rb
    home_cm = _pick_best_player(hp, {"CDM", "DM", "CM", "CAM", "AM"}, "control", fallback_role="MID")

    away_lb = _pick_best_player(ap, {"LB", "LWB"}, "defense", fallback_role="DEF")
    away_rb_pool = [p for p in ap if p is not away_lb]
    away_rb = _pick_best_player(away_rb_pool, {"RB", "RWB"}, "defense", fallback_role="DEF") or away_lb
    away_cb_pool = [p for p in ap if p is not away_lb and p is not away_rb]
    away_cb = _pick_best_player(away_cb_pool, {"CB"}, "defense", fallback_role="DEF") or away_rb
    away_cm = _pick_best_player(ap, {"CDM", "DM", "CM", "CAM", "AM"}, "control", fallback_role="MID")

    home_duels = [
        ("Left Flank", home_lw, away_rb, False),
        ("Right Flank", home_rw, away_lb, False),
        ("Central 9", home_st, away_cb, True),
        ("Midfield Control", home_cm, away_cm, False),
    ]
    away_duels = [
        ("Left Flank", away_lw, home_rb, False),
        ("Right Flank", away_rw, home_lb, False),
        ("Central 9", away_st, home_cb, True),
    ]

    home_scores = []
    away_scores = []
    highlights = []
    position_battles = []

    for label, att, deff, central in home_duels:
        if att and deff:
            if label == "Midfield Control":
                score = _midfield_duel_score(att, deff)
            else:
                score = _duel_score(att, deff, central=central)
            home_scores.append(score)
            highlights.append(f"Home {label}: {att['name']} vs {deff['name']} ({score:+.2f})")
            position_battles.append(
                {
                    "perspective": "home",
                    "zone": label,
                    "attacker": att["name"],
                    "defender": deff["name"],
                    "attack_value": float(_safe_float(att.get("attack"), 0.0)),
                    "defense_value": float(_safe_float(deff.get("defense"), 0.0)),
                    "xg_p90": float(_safe_float(att.get("xg_p90"), 0.0)),
                    "xa_p90": float(_safe_float(att.get("xa_p90"), 0.0)),
                    "xt_proxy": float(_safe_float(att.get("xt_proxy"), 0.0)),
                    "duel_score": float(score),
                    "edge": _duel_edge(score, perspective="home"),
                }
            )

    for label, att, deff, central in away_duels:
        if att and deff:
            score = _duel_score(att, deff, central=central)
            away_scores.append(score)
            highlights.append(f"Away {label}: {att['name']} vs {deff['name']} ({score:+.2f})")
            position_battles.append(
                {
                    "perspective": "away",
                    "zone": label,
                    "attacker": att["name"],
                    "defender": deff["name"],
                    "attack_value": float(_safe_float(att.get("attack"), 0.0)),
                    "defense_value": float(_safe_float(deff.get("defense"), 0.0)),
                    "xg_p90": float(_safe_float(att.get("xg_p90"), 0.0)),
                    "xa_p90": float(_safe_float(att.get("xa_p90"), 0.0)),
                    "xt_proxy": float(_safe_float(att.get("xt_proxy"), 0.0)),
                    "duel_score": float(score),
                    "edge": _duel_edge(score, perspective="away"),
                }
            )

    home_edge = float(np.mean(home_scores)) if home_scores else 0.0
    away_edge = float(np.mean(away_scores)) if away_scores else 0.0

    return {
        "home_adj": float(_clip(home_edge * 0.08, -0.05, 0.06)),
        "away_adj": float(_clip(away_edge * 0.08, -0.05, 0.06)),
        "highlights": highlights[:4],
        "position_battles": position_battles[:8],
    }


def _load_match_dates(league, team_name):
    if pd is None:
        return []

    log_file = _find_match_log_file(league, team_name)
    if not log_file:
        return []

    try:
        df = pd.read_excel(log_file, sheet_name="Shooting")
    except Exception:
        try:
            df = pd.read_excel(log_file, sheet_name=0)
        except Exception:
            return []

    if df.empty:
        return []

    date_col = None
    for col in df.columns:
        col_text = str(col).lower()
        if col_text == "date" or col_text.endswith("_date"):
            date_col = col
            break

    if not date_col:
        return []

    dates = pd.to_datetime(df[date_col], errors="coerce").dropna().dt.normalize()
    if dates.empty:
        return []

    today = pd.Timestamp.now().normalize()
    dates = dates[dates <= today]
    if dates.empty:
        return []

    return list(dates.drop_duplicates().sort_values(ascending=False))


def _compute_fatigue(league, team_name, load_index):
    dates = _load_match_dates(league, team_name)
    if not dates:
        return {
            "attack_penalty": 0.0,
            "defense_leak": 0.0,
            "days_since_last": None,
            "matches_7d": 0,
            "matches_14d": 0,
        }

    today = pd.Timestamp.now().normalize()
    last_date = dates[0]
    days_since = int((today - last_date).days)

    matches_7d = sum(1 for d in dates if d >= (today - timedelta(days=7)))
    matches_14d = sum(1 for d in dates if d >= (today - timedelta(days=14)))
    matches_21d = sum(1 for d in dates if d >= (today - timedelta(days=21)))

    pressure = 0.0
    if days_since <= 1:
        pressure += 0.028
    elif days_since == 2:
        pressure += 0.016
    elif days_since == 3:
        pressure += 0.008

    pressure += max(0, matches_7d - 1) * 0.012
    pressure += max(0, matches_14d - 3) * 0.008
    pressure += max(0, matches_21d - 5) * 0.005

    factor = 0.85 + (_clip(load_index, 0.5, 1.2) * 0.45)
    attack_penalty = _clip(pressure * factor, 0.0, 0.095)

    return {
        "attack_penalty": float(attack_penalty),
        "defense_leak": float(_clip(attack_penalty * 0.55, 0.0, 0.060)),
        "days_since_last": days_since,
        "matches_7d": int(matches_7d),
        "matches_14d": int(matches_14d),
    }


def _flow_num(flow, keys):
    if not isinstance(flow, dict):
        return None
    for key in keys:
        if key not in flow:
            continue
        val = _safe_float(flow.get(key), None)
        if val is not None:
            return val
    return None


def _normalize_field_tilt(value):
    if value is None:
        return 0.5
    tilt = float(value)
    if tilt > 1.5:
        tilt = tilt / 100.0
    return _clip(tilt, 0.0, 1.0)


def _build_tactical_inputs(flow_team, flow_opp):
    ppda_team_raw = _flow_num(flow_team, ["calc_PPDA", "PPDA"])
    ppda_opp_raw = _flow_num(flow_opp, ["calc_PPDA", "PPDA"])
    field_tilt_raw = _flow_num(flow_team, ["calc_FieldTilt_Pct", "FieldTilt_Pct"])
    high_error_raw = _flow_num(flow_team, ["calc_HighError_Rate", "HighError_Rate"])
    directness_raw = _flow_num(flow_team, ["calc_Directness", "Directness"])
    big_chance_raw = _flow_num(flow_team, ["calc_BigChance_Diff", "BigChance_Diff"])

    available = [
        ppda_team_raw is not None,
        ppda_opp_raw is not None,
        field_tilt_raw is not None,
        high_error_raw is not None,
        directness_raw is not None,
        big_chance_raw is not None,
    ]
    completeness = float(sum(available) / len(available))

    ppda_team = _safe_float(ppda_team_raw, 8.0)
    ppda_opp = _safe_float(ppda_opp_raw, 8.0)
    field_tilt = _normalize_field_tilt(field_tilt_raw)
    high_error_rate = _safe_float(high_error_raw, 12.0)
    directness = _safe_float(directness_raw, 0.08)
    big_chance_diff = _safe_float(big_chance_raw, 0.0)

    pressing_edge = _clip((ppda_opp - ppda_team) / max(2.5, ppda_opp), -1.0, 1.0)
    tilt_edge = _clip((field_tilt - 0.5) / 0.5, -1.0, 1.0)
    high_error_norm = _clip(high_error_rate / 22.0, 0.0, 1.0)
    directness_norm = _clip(directness / 0.18, 0.0, 1.0)
    big_chance_norm = _clip(big_chance_diff / 14.0, -1.0, 1.0)

    tempo = _clip((0.55 * directness_norm) + (0.45 * high_error_norm), 0.0, 1.0)
    raw_attack_signal = (
        (0.42 * pressing_edge)
        + (0.26 * tilt_edge)
        + (0.20 * big_chance_norm)
        + (0.12 * (tempo - 0.5))
    )
    confidence = 0.55 + (0.45 * completeness)
    attack_signal = _clip(raw_attack_signal * confidence, -1.0, 1.0)
    attack_adj = _clip(attack_signal * 0.055, -0.045, 0.055)

    return {
        "ppda": float(ppda_team),
        "ppda_opp": float(ppda_opp),
        "field_tilt": float(field_tilt),
        "high_error_rate": float(high_error_rate),
        "directness": float(directness),
        "big_chance_diff": float(big_chance_diff),
        "pressing_edge": float(pressing_edge),
        "tempo": float(tempo),
        "completeness": float(completeness),
        "attack_signal": float(attack_signal),
        "attack_adjustment": float(attack_adj),
    }


def _progression_strength(prog):
    if not prog:
        return 0.5

    xt_proxy = _safe_float(prog.get("xt_proxy"), 0.5)
    deep_completion = _safe_float(prog.get("deep_completion_proxy"), 0.0)
    prog_runs = _safe_float(prog.get("progressive_runs_proxy"), 0.0)
    counter_idx = _safe_float(prog.get("counter_punch_index"), 0.0)
    u_shape_risk = _safe_float(prog.get("u_shape_risk"), 0.0)

    strength = (
        0.62 * xt_proxy
        + 0.18 * _tanh_norm(deep_completion, 18.0)
        + 0.12 * _tanh_norm(prog_runs, 10.0)
        + 0.12 * counter_idx
        - 0.10 * u_shape_risk
    )
    return float(_clip(strength, 0.0, 1.2))


def simulate_match(
    home_xg,
    away_xg,
    home_sofascore=None,
    away_sofascore=None,
    iterations=10000,
    league=None,
    home_team=None,
    away_team=None,
    context_text=None,
    home_progression=None,
    away_progression=None,
    home_flow=None,
    away_flow=None,
):
    """
    Simulator v9
    - Keeps v8 base (xG + goals/90 + shrinkage + Dixon-Coles)
    - Adds Dynamic Lineup Strength from player-level data
    - Adds Key Matchups (position-vs-position)
    - Adds Fatigue adjustments from match logs
    - Adds xT/Progression proxy adjustments
    """
    h_att = _safe_float(home_xg.get("attack", {}).get("xg_per_game"), 1.25)
    h_def = _safe_float(home_xg.get("defense", {}).get("xga_per_game"), 1.20)
    a_att = _safe_float(away_xg.get("attack", {}).get("xg_per_game"), 1.25)
    a_def = _safe_float(away_xg.get("defense", {}).get("xga_per_game"), 1.20)

    xg_home = (h_att + a_def) / 2.0
    xg_away = (a_att + h_def) / 2.0

    has_ss = home_sofascore is not None and away_sofascore is not None
    if has_ss:
        h_gf = _safe_float(home_sofascore.get("goals_scored_per_game"), xg_home)
        h_ga = _safe_float(home_sofascore.get("goals_conceded_per_game"), h_def)
        a_gf = _safe_float(away_sofascore.get("goals_scored_per_game"), xg_away)
        a_ga = _safe_float(away_sofascore.get("goals_conceded_per_game"), a_def)
        goals_home = (h_gf + a_ga) / 2.0
        goals_away = (a_gf + h_ga) / 2.0
        w_xg, w_goals = 0.58, 0.42
    else:
        goals_home, goals_away = xg_home, xg_away
        w_xg, w_goals = 1.0, 0.0

    base_home = (w_xg * xg_home) + (w_goals * goals_home)
    base_away = (w_xg * xg_away) + (w_goals * goals_away)

    prior_home, prior_away = 1.35, 1.20
    shr = 0.86
    reg_home = (shr * base_home) + ((1 - shr) * prior_home)
    reg_away = (shr * base_away) + ((1 - shr) * prior_away)

    # Calibrated to keep baseline home tilt near ~5-6% (including prior shrinkage effect).
    home_adv, away_dis = 1.034, 0.996
    h_form = _safe_float(home_xg.get("form_last_5"), 7.5)
    a_form = _safe_float(away_xg.get("form_last_5"), 7.5)
    form_adj = _clip(((h_form - a_form) / 15.0) * 0.08, -0.04, 0.04)

    strength_raw = math.log((reg_home + 0.05) / (reg_away + 0.05))
    strength_adj = _clip(math.tanh(strength_raw) * 0.06, -0.06, 0.06)

    lambda_home = reg_home * home_adv * (1.0 + form_adj + strength_adj)
    lambda_away = reg_away * away_dis * (1.0 - form_adj - strength_adj)

    # Winner mentality signal (v7.1 spirit, moderated for v9 stability).
    home_ratio = reg_home / max(1e-9, reg_away)
    away_ratio = reg_away / max(1e-9, reg_home)
    ratio_threshold = 1.12
    home_math_bonus = 0.0
    away_math_bonus = 0.0
    math_winner_side = "none"
    if home_ratio > ratio_threshold and home_ratio >= away_ratio:
        home_math_bonus = _clip((home_ratio - ratio_threshold) * 0.045, 0.0, 0.030)
        math_winner_side = "home"
    elif away_ratio > ratio_threshold:
        away_math_bonus = _clip((away_ratio - ratio_threshold) * 0.045, 0.0, 0.030)
        math_winner_side = "away"

    lambda_home *= 1.0 + home_math_bonus
    lambda_away *= 1.0 + away_math_bonus

    lineup_ctx = {
        "home_source": "off",
        "away_source": "off",
        "home_matched": 0,
        "away_matched": 0,
        "home_lineup_metrics": None,
        "away_lineup_metrics": None,
        "confidence": 0.0,
    }
    fatigue_ctx = {
        "home_attack_penalty": 0.0,
        "away_attack_penalty": 0.0,
    }
    calibration_ctx = {
        "enabled": False,
        "path": CALIBRATION_PATH,
        "home_multiplier": 1.0,
        "away_multiplier": 1.0,
    }
    progression_ctx = {
        "home_xt_proxy": None,
        "away_xt_proxy": None,
        "home_strength": None,
        "away_strength": None,
    }
    tactical_ctx = {
        "enabled": False,
        "home": {},
        "away": {},
        "home_adjustment": 0.0,
        "away_adjustment": 0.0,
    }
    key_matchups = []
    position_battles = []
    math_winner_ctx = {
        "winner_side": math_winner_side,
        "home_ratio": float(home_ratio),
        "away_ratio": float(away_ratio),
        "home_bonus": float(home_math_bonus),
        "away_bonus": float(away_math_bonus),
        "ratio_threshold": float(ratio_threshold),
    }

    lineup_quality_adj = 0.0
    home_matchup_adj = 0.0
    away_matchup_adj = 0.0
    progression_home_adj = 0.0
    progression_away_adj = 0.0
    tactical_home_adj = 0.0
    tactical_away_adj = 0.0

    home_fatigue = {"attack_penalty": 0.0, "defense_leak": 0.0}
    away_fatigue = {"attack_penalty": 0.0, "defense_leak": 0.0}

    # Apply xT/progression proxy before lineup and fatigue layers.
    home_prog_strength = _progression_strength(home_progression)
    away_prog_strength = _progression_strength(away_progression)
    progression_edge = _clip((home_prog_strength - away_prog_strength) * 0.10, -0.055, 0.055)

    home_counter = _safe_float((home_progression or {}).get("counter_punch_index"), 0.0)
    away_counter = _safe_float((away_progression or {}).get("counter_punch_index"), 0.0)
    home_u_shape = _safe_float((home_progression or {}).get("u_shape_risk"), 0.0)
    away_u_shape = _safe_float((away_progression or {}).get("u_shape_risk"), 0.0)

    counter_home = _clip((home_counter - away_u_shape) * 0.02, -0.02, 0.02)
    counter_away = _clip((away_counter - home_u_shape) * 0.02, -0.02, 0.02)

    progression_home_adj = progression_edge + counter_home
    progression_away_adj = (-progression_edge) + counter_away

    lambda_home *= 1.0 + progression_home_adj
    lambda_away *= 1.0 + progression_away_adj

    progression_ctx = {
        "home_xt_proxy": (home_progression or {}).get("xt_proxy"),
        "away_xt_proxy": (away_progression or {}).get("xt_proxy"),
        "home_strength": home_prog_strength,
        "away_strength": away_prog_strength,
        "home_adjustment": progression_home_adj,
        "away_adjustment": progression_away_adj,
        "home_counter_index": home_counter,
        "away_counter_index": away_counter,
        "home_u_shape_risk": home_u_shape,
        "away_u_shape_risk": away_u_shape,
    }

    if isinstance(home_flow, dict) and isinstance(away_flow, dict):
        home_tactical = _build_tactical_inputs(home_flow, away_flow)
        away_tactical = _build_tactical_inputs(away_flow, home_flow)

        tactical_home_adj = home_tactical["attack_adjustment"]
        tactical_away_adj = away_tactical["attack_adjustment"]
        lambda_home *= 1.0 + tactical_home_adj
        lambda_away *= 1.0 + tactical_away_adj

        tactical_ctx = {
            "enabled": True,
            "home": home_tactical,
            "away": away_tactical,
            "home_adjustment": float(tactical_home_adj),
            "away_adjustment": float(tactical_away_adj),
        }

    try:
        if league and home_team and away_team and pd is not None:
            parsed_lineups = _parse_confirmed_lineups(context_text, home_team, away_team)

            home_df = _load_team_player_frame(league, home_team)
            away_df = _load_team_player_frame(league, away_team)

            if home_df is not None and not home_df.empty and away_df is not None and not away_df.empty:
                home_profile = _build_team_profile(home_df, parsed_lineups.get("home"))
                away_profile = _build_team_profile(away_df, parsed_lineups.get("away"))

                if home_profile and away_profile:
                    lineup_ctx = {
                        "home_source": home_profile["source"],
                        "away_source": away_profile["source"],
                        "home_matched": home_profile["matched_count"],
                        "away_matched": away_profile["matched_count"],
                        "home_lineup_metrics": {
                            "attack": home_profile["actual"]["attack"],
                            "defense": home_profile["actual"]["defense"],
                            "overall": home_profile["actual"]["overall"],
                            "xg_p90": home_profile["actual"].get("xg_p90"),
                            "xa_p90": home_profile["actual"].get("xa_p90"),
                            "xt_proxy": home_profile["actual"].get("xt_proxy"),
                        },
                        "away_lineup_metrics": {
                            "attack": away_profile["actual"]["attack"],
                            "defense": away_profile["actual"]["defense"],
                            "overall": away_profile["actual"]["overall"],
                            "xg_p90": away_profile["actual"].get("xg_p90"),
                            "xa_p90": away_profile["actual"].get("xa_p90"),
                            "xt_proxy": away_profile["actual"].get("xt_proxy"),
                        },
                        "confidence": float(_clip((home_profile["matched_count"] + away_profile["matched_count"]) / 22.0, 0.0, 1.0)),
                    }

                    lineup_quality_adj = _clip(
                        (home_profile["actual"]["overall"] - away_profile["actual"]["overall"]) * 0.08,
                        -0.07,
                        0.07,
                    )

                    home_attack_delta_adj = _clip(home_profile["attack_delta"] * 0.55, -0.10, 0.08)
                    away_attack_delta_adj = _clip(away_profile["attack_delta"] * 0.55, -0.10, 0.08)
                    home_defense_delta_opp = _clip(-home_profile["defense_delta"] * 0.42, -0.07, 0.08)
                    away_defense_delta_opp = _clip(-away_profile["defense_delta"] * 0.42, -0.07, 0.08)

                    lambda_home *= 1.0 + lineup_quality_adj
                    lambda_away *= 1.0 - lineup_quality_adj
                    lambda_home *= 1.0 + home_attack_delta_adj + away_defense_delta_opp
                    lambda_away *= 1.0 + away_attack_delta_adj + home_defense_delta_opp

                    matchup_data = _derive_matchups(home_profile, away_profile)
                    home_matchup_adj = matchup_data["home_adj"]
                    away_matchup_adj = matchup_data["away_adj"]
                    key_matchups = matchup_data["highlights"]
                    position_battles = matchup_data.get("position_battles", [])

                    lambda_home *= 1.0 + home_matchup_adj
                    lambda_away *= 1.0 + away_matchup_adj

                    home_fatigue = _compute_fatigue(league, home_team, home_profile["actual"]["load_index"])
                    away_fatigue = _compute_fatigue(league, away_team, away_profile["actual"]["load_index"])

                    lambda_home *= 1.0 - home_fatigue["attack_penalty"]
                    lambda_away *= 1.0 - away_fatigue["attack_penalty"]
                    lambda_home *= 1.0 + away_fatigue["defense_leak"]
                    lambda_away *= 1.0 + home_fatigue["defense_leak"]

                    fatigue_ctx = {
                        "home_attack_penalty": home_fatigue["attack_penalty"],
                        "away_attack_penalty": away_fatigue["attack_penalty"],
                        "home_days_since_last": home_fatigue.get("days_since_last"),
                        "away_days_since_last": away_fatigue.get("days_since_last"),
                    }
    except Exception:
        # v9 signals are additive; if anything fails, we keep v8-compatible behavior.
        pass

    calibration = _load_model_calibration(CALIBRATION_PATH)
    lambda_home, lambda_away, calibration_ctx = _apply_model_calibration(
        lambda_home=lambda_home,
        lambda_away=lambda_away,
        calibration=calibration,
        league=league,
        home_team=home_team,
        away_team=away_team,
    )

    lambda_home = _clip(lambda_home, 0.25, 3.8)
    lambda_away = _clip(lambda_away, 0.25, 3.8)

    post_strength_raw = math.log((lambda_home + 0.05) / (lambda_away + 0.05))
    close = _clip(1.0 - abs(post_strength_raw) / 1.2, 0.0, 1.0)
    rho = -0.03 - (0.07 * close)

    if tactical_ctx.get("enabled"):
        home_tempo = _safe_float(tactical_ctx.get("home", {}).get("tempo"), 0.5)
        away_tempo = _safe_float(tactical_ctx.get("away", {}).get("tempo"), 0.5)
        tempo = _clip((home_tempo + away_tempo) / 2.0, 0.0, 1.0)

        home_sig = _safe_float(tactical_ctx.get("home", {}).get("attack_signal"), 0.0)
        away_sig = _safe_float(tactical_ctx.get("away", {}).get("attack_signal"), 0.0)
        balance = _clip(1.0 - abs(home_sig - away_sig), 0.0, 1.0)

        rho += (tempo - 0.5) * 0.04
        rho += (0.5 - balance) * 0.03
        rho = _clip(rho, -0.13, -0.01)

        tactical_ctx["tempo"] = float(tempo)
        tactical_ctx["balance"] = float(balance)
        tactical_ctx["rho_adjustment"] = float(rho + (0.03 + (0.07 * close)))
    else:
        tactical_ctx["tempo"] = None
        tactical_ctx["balance"] = None
        tactical_ctx["rho_adjustment"] = 0.0

    prob_matrix = _build_score_matrix(lambda_home, lambda_away, max_goals=10, rho=rho)

    home_win_prob = float(np.tril(prob_matrix, k=-1).sum() * 100)
    draw_prob = float(np.trace(prob_matrix) * 100)
    away_win_prob = float(np.triu(prob_matrix, k=1).sum() * 100)

    top3 = _top_scores(prob_matrix, top_n=3)
    best = top3[0]
    most_likely_score = f"{best[0]}-{best[1]}"
    top3_scores = ", ".join([f"{h}-{a} ({p*100:.1f}%)" for h, a, p in top3])

    bonus_parts = [
        f"HomeAdv x{home_adv:.2f}",
        f"Form {form_adj*100:+.1f}%",
        f"Strength {strength_adj*100:+.1f}%",
    ]
    if abs(lineup_quality_adj) > 1e-6:
        bonus_parts.append(f"Lineup {lineup_quality_adj*100:+.1f}%")
    if home_math_bonus > 1e-6 or away_math_bonus > 1e-6:
        bonus_parts.append(f"MathWinner H{home_math_bonus*100:+.1f}% A{away_math_bonus*100:+.1f}%")
    if abs(progression_home_adj) > 1e-6 or abs(progression_away_adj) > 1e-6:
        bonus_parts.append(f"Progression H{progression_home_adj*100:+.1f}% A{progression_away_adj*100:+.1f}%")
    if tactical_ctx.get("enabled"):
        bonus_parts.append(f"Tactical H{tactical_home_adj*100:+.1f}% A{tactical_away_adj*100:+.1f}%")
        tempo_txt = _safe_float(tactical_ctx.get("tempo"), None)
        balance_txt = _safe_float(tactical_ctx.get("balance"), None)
        if tempo_txt is not None and balance_txt is not None:
            bonus_parts.append(f"Tactical tempo {tempo_txt:.2f} balance {balance_txt:.2f}")
    if abs(home_matchup_adj) > 1e-6 or abs(away_matchup_adj) > 1e-6:
        bonus_parts.append(f"Matchups H{home_matchup_adj*100:+.1f}% A{away_matchup_adj*100:+.1f}%")
    if home_fatigue["attack_penalty"] > 0 or away_fatigue["attack_penalty"] > 0:
        bonus_parts.append(
            f"Fatigue H-{home_fatigue['attack_penalty']*100:.1f}% A-{away_fatigue['attack_penalty']*100:.1f}%"
        )
    if calibration_ctx.get("enabled"):
        bonus_parts.append(
            f"Calibration Hx{calibration_ctx.get('home_multiplier', 1.0):.3f} Ax{calibration_ctx.get('away_multiplier', 1.0):.3f}"
        )
    bonus_parts.append(f"DC rho {rho:.3f}")

    return {
        "home_win_prob": home_win_prob,
        "draw_prob": draw_prob,
        "away_win_prob": away_win_prob,
        "expected_goals_home": float(lambda_home),
        "expected_goals_away": float(lambda_away),
        "most_likely_score": most_likely_score,
        "top3_scores": top3_scores,
        "base_exp_home": float(base_home),
        "base_exp_away": float(base_away),
        "bonus_applied": " | ".join(bonus_parts),
        "model_version": "v9",
        "lineup_context": lineup_ctx,
        "fatigue_context": fatigue_ctx,
        "calibration_context": calibration_ctx,
        "progression_context": progression_ctx,
        "tactical_context": tactical_ctx,
        "key_matchups": key_matchups,
        "position_battles": position_battles,
        "math_winner_context": math_winner_ctx,
    }


if __name__ == "__main__":
    h_xg = {"attack": {"xg_per_game": 1.6}, "defense": {"xga_per_game": 1.1}, "form_last_5": 10}
    a_xg = {"attack": {"xg_per_game": 1.4}, "defense": {"xga_per_game": 1.3}, "form_last_5": 7}
    sim = simulate_match(
        h_xg,
        a_xg,
        None,
        None,
        league="Premier_League",
        home_team="Arsenal",
        away_team="Liverpool",
        context_text="",
    )
    print(sim)
