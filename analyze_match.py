
import argparse
import json
import math
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TEAM_NAME_MAP = {
    "Paris S-G": "Paris Saint-Germain",
    "PSG": "Paris Saint-Germain",
    "Rennes": "Stade Rennais",
    "Lyon": "Olympique Lyonnais",
    "Marseille": "Olympique de Marseille",
    "Monaco": "AS Monaco",
    "Nice": "OGC Nice",
    "Lille": "LOSC Lille",
    "Brest": "Stade Brestois",
    "Man Utd": "Manchester United",
    "Manchester Utd": "Manchester United",
    "Sheffield Utd": "Sheffield United",
    "Nott'm Forest": "Nottingham Forest",
    "Wolves": "Wolverhampton",
    "Brighton": "Brighton & Hove Albion",
}

TEAM_SUFFIX_TOKENS = {"fc", "cf", "sc", "afc", "ac"}
SCORE_PAIR_RE = re.compile(r"^\s*(\d+)\s*[-:]\s*(\d+)\s*$")


def normalize_team_name(name):
    return TEAM_NAME_MAP.get(str(name).strip(), str(name).strip())


def _normalize_text(value):
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^0-9a-zA-Z\s]", " ", text).lower()
    return re.sub(r"\s+", " ", text).strip()


def _canonical_team_name(name):
    base = normalize_team_name(name)
    tokens = [t for t in str(base).split() if _normalize_text(t) not in TEAM_SUFFIX_TOKENS]
    return " ".join(tokens) if tokens else str(base)


def _team_slug(name):
    tokens = [t for t in _normalize_text(_canonical_team_name(name)).split() if t]
    return "_".join(t.capitalize() for t in tokens) if tokens else "Unknown"


def _analysis_path(home, away):
    return f"analyses/analysis_{_team_slug(home)}_{_team_slug(away)}.md"


def _team_aliases(name):
    items = {str(name).strip(), normalize_team_name(name), _canonical_team_name(name)}
    out, seen = [], set()
    for item in items:
        key = _normalize_text(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _find_team_row(df, team_col, team_name):
    if df is None or df.empty or team_col not in df.columns:
        return None
    series = df[team_col].astype(str)
    for alias in _team_aliases(team_name):
        mask = series.str.contains(re.escape(alias), case=False, na=False)
        if mask.any():
            return df.loc[mask].iloc[0]
    target = _normalize_text(team_name)
    norm = series.apply(_normalize_text)
    mask = (norm == target) | norm.str.contains(target, regex=False, na=False)
    if mask.any():
        return df.loc[mask].iloc[0]
    return None


def _to_number(value):
    try:
        num = float(value)
    except Exception:
        return None
    if pd.isna(num):
        return None
    return num


def _per90_from_row(row, per90_key, raw_key, default=0.0):
    per90_val = _to_number(row.get(per90_key))
    if per90_val is not None:
        return per90_val

    raw_val = _to_number(row.get(raw_key))
    matches_played = _to_number(row.get("Matches_Played"))
    if raw_val is None or matches_played is None or matches_played <= 0:
        return default
    return raw_val / matches_played


def find_team_league(team_name):
    base = Path("sofaplayer")
    if not base.exists():
        return None
    aliases = [_normalize_text(a) for a in _team_aliases(team_name)]
    for league_dir in base.iterdir():
        if not league_dir.is_dir():
            continue
        for f in league_dir.glob("*_stats.xlsx"):
            stem = _normalize_text(f.stem.replace("_stats", ""))
            if any(alias and (alias in stem or stem in alias) for alias in aliases):
                return league_dir.name
    return None


def get_simulation_stats(team_name, league):
    file_path = Path("sofascore_team_data") / f"{league}_Team_Stats.xlsx"
    if not file_path.exists():
        return None
    try:
        df = pd.read_excel(file_path)
        row = _find_team_row(df, "Team_Name", team_name)
        if row is None:
            return None
        goals_scored_p90 = _per90_from_row(row, "goalsScored_per_90", "goalsScored", default=0.0)
        goals_conceded_p90 = _per90_from_row(row, "goalsConceded_per_90", "goalsConceded", default=0.0)
        return {
            "goals_scored_per_game": float(goals_scored_p90),
            "goals_conceded_per_game": float(goals_conceded_p90),
        }
    except Exception:
        return None


def get_progression_stats(team_name, league):
    file_path = Path("sofascore_team_data") / f"{league}_Team_Stats.xlsx"
    if not file_path.exists():
        return {}
    try:
        df = pd.read_excel(file_path)
        row = _find_team_row(df, "Team_Name", team_name)
        if row is None:
            return {}
        opp_half_passes_p90 = _per90_from_row(
            row, "accurateOppositionHalfPasses_per_90", "accurateOppositionHalfPasses", default=0.0
        )
        dribbles_p90 = _per90_from_row(row, "successfulDribbles_per_90", "successfulDribbles", default=0.0)
        big_created_p90 = _per90_from_row(row, "bigChancesCreated_per_90", "bigChancesCreated", default=0.0)
        inside_box_shots_p90 = _per90_from_row(
            row, "shotsFromInsideTheBox_per_90", "shotsFromInsideTheBox", default=0.0
        )
        fast_breaks_p90 = _per90_from_row(row, "fastBreaks_per_90", "fastBreaks", default=0.0)
        corners_p90 = _per90_from_row(row, "corners_per_90", "corners", default=0.0)
        shots_on_target_p90 = _per90_from_row(row, "shotsOnTarget_per_90", "shotsOnTarget", default=0.0)
        long_balls_p90 = _per90_from_row(row, "accurateLongBalls_per_90", "accurateLongBalls", default=0.0)

        deep_completion_proxy = (0.9 * big_created_p90) + (0.22 * inside_box_shots_p90) + (0.75 * fast_breaks_p90)
        progressive_runs_proxy = (0.5 * dribbles_p90) + (1.1 * fast_breaks_p90)
        xt_proxy = max(0.0, min(1.0, 0.36 * math.tanh(opp_half_passes_p90 / 240.0) + 0.24 * math.tanh(dribbles_p90 / 10.0) + 0.24 * math.tanh(deep_completion_proxy / 7.0)))
        counter_punch_index = max(0.0, min(1.0, math.tanh((0.8 * fast_breaks_p90) / 3.5)))
        u_shape_risk = max(0.0, min(1.0, math.tanh((opp_half_passes_p90 / max(1.0, deep_completion_proxy * 25.0)) / 1.5) * (1.0 - xt_proxy)))

        return {
            "xt_proxy": float(xt_proxy),
            "deep_completion_proxy": float(deep_completion_proxy),
            "progressive_runs_proxy": float(progressive_runs_proxy),
            "u_shape_risk": float(u_shape_risk),
            "counter_punch_index": float(counter_punch_index),
            "prg_pass_dist": float(opp_half_passes_p90),
            "prg_carry_dist": float(dribbles_p90),
            "big_created_p90": float(big_created_p90),
            "inside_box_shots_p90": float(inside_box_shots_p90),
            "fast_breaks_p90": float(fast_breaks_p90),
            "corners_p90": float(corners_p90),
            "shots_on_target_p90": float(shots_on_target_p90),
            "long_balls_p90": float(long_balls_p90),
            "source": "team_stats_fallback",
        }
    except Exception:
        return {}

def _load_live_context(path="match_context.txt"):
    if not os.path.exists(path):
        return "No live context available (Lineups/Injuries missing)."
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "No live context available (Lineups/Injuries missing)."


def _parse_context_headers(context_text):
    headers = {"match": None, "date": None, "league": None}
    for raw_line in str(context_text).splitlines():
        line = re.sub(r"[*_`#>\[\]]", "", raw_line).strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        k = _normalize_text(key)
        v = value.strip()
        if k == "match":
            headers["match"] = v
        elif k == "date":
            headers["date"] = v
        elif k == "league":
            headers["league"] = v
    return headers


def _split_players(blob):
    clean = re.sub(r"\([^)]*\)", "", blob)
    clean = re.sub(r"[*_`#>\[\]]", "", clean)
    out = []
    for token in clean.replace(";", ",").split(","):
        token = token.strip(" .:-")
        if token and token.lower() not in {"n/a", "na", "none", "..."}:
            out.append(token)
    return out


def _team_side(label, home_team, away_team):
    label_n = _normalize_text(label)
    if not label_n:
        return None
    for alias in _team_aliases(home_team):
        a = _normalize_text(alias)
        if a and (a == label_n or a in label_n or label_n in a):
            return "home"
    for alias in _team_aliases(away_team):
        a = _normalize_text(alias)
        if a and (a == label_n or a in label_n or label_n in a):
            return "away"
    return None


def _extract_lineup_missing_conflicts(context_text, home_team, away_team):
    lineups = {"home": set(), "away": set()}
    missings = {"home": set(), "away": set()}
    in_lineups = False
    current_side = None

    for raw_line in str(context_text).splitlines():
        line = re.sub(r"[*_`#>\[\]]", "", raw_line).strip()
        if not line:
            continue
        lower = line.lower()

        if "confirmed lineup" in lower or "confirmed lineups" in lower:
            in_lineups = True
            current_side = None
            continue

        if "team news" in lower or lower.startswith("context"):
            in_lineups = False
            current_side = None

        if in_lineups and ":" in line and "(" in line and ")" in line:
            label = line.split("(", 1)[0].strip().rstrip(":")
            side = _team_side(label, home_team, away_team)
            if side:
                current_side = side
                continue

        if in_lineups and current_side and raw_line.strip().startswith("*"):
            bullet = line
            if ":" in bullet:
                _, rhs = bullet.split(":", 1)
                for p in _split_players(rhs):
                    lineups[current_side].add(p)
            else:
                for p in _split_players(bullet):
                    lineups[current_side].add(p)

        if "missing" in lower and ":" in line:
            left, right = line.split(":", 1)
            m = re.search(r"(.+?)\s+missing$", left.strip(), flags=re.IGNORECASE)
            if m:
                side = _team_side(m.group(1).strip(), home_team, away_team)
                if side:
                    for p in _split_players(right):
                        missings[side].add(p)

    flags = []
    for side, display in (("home", home_team), ("away", away_team)):
        lineup_n = {_normalize_text(x): x for x in lineups[side] if _normalize_text(x)}
        missing_n = {_normalize_text(x): x for x in missings[side] if _normalize_text(x)}
        overlap = sorted(set(lineup_n).intersection(set(missing_n)))
        if overlap:
            names = [lineup_n.get(k, missing_n.get(k, k)) for k in overlap[:6]]
            flags.append(f"{display}: players appear in both lineup and missing list -> {', '.join(names)}.")
    return flags


def run_data_qc(home_team, away_team, league, context_text, home_league=None, away_league=None):
    flags = []
    headers = _parse_context_headers(context_text)

    if home_league and away_league and home_league != away_league:
        flags.append(f"League mismatch from datasets: home={home_league}, away={away_league}. Using '{league}'.")

    if headers.get("match"):
        match_norm = _normalize_text(headers["match"])
        if _normalize_text(home_team) not in match_norm or _normalize_text(away_team) not in match_norm:
            flags.append(f"Context match header '{headers['match']}' does not match requested fixture '{home_team} vs {away_team}'.")

    if headers.get("league"):
        l1 = _normalize_text(str(league).replace("_", " "))
        l2 = _normalize_text(str(headers["league"]).replace("_", " "))
        if l1 and l2 and l1 != l2:
            flags.append(f"Context league header '{headers['league']}' differs from detected league '{league}'.")

    flags.extend(_extract_lineup_missing_conflicts(context_text, home_team, away_team))
    return flags, headers


def _build_poisson_matrix(lambda_home, lambda_away, max_goals=10):
    lambda_home = max(0.0, float(lambda_home))
    lambda_away = max(0.0, float(lambda_away))
    home = [math.exp(-lambda_home) * (lambda_home ** g) / math.factorial(g) for g in range(max_goals)]
    away = [math.exp(-lambda_away) * (lambda_away ** g) / math.factorial(g) for g in range(max_goals)]
    return [[home[h] * away[a] for a in range(max_goals)] for h in range(max_goals)]


def _result_from_score(score):
    try:
        h, a = [int(x) for x in str(score).split("-", 1)]
    except Exception:
        return None
    if h > a:
        return "Home"
    if h < a:
        return "Away"
    return "Draw"


def _parse_score_pair(score_text):
    if score_text is None:
        return None
    m = SCORE_PAIR_RE.match(str(score_text))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _score_probability(lambda_home, lambda_away, home_goals, away_goals):
    if home_goals < 0 or away_goals < 0:
        return 0.0
    lam_h = max(0.0, float(lambda_home))
    lam_a = max(0.0, float(lambda_away))
    p_h = math.exp(-lam_h) * (lam_h ** int(home_goals)) / math.factorial(int(home_goals))
    p_a = math.exp(-lam_a) * (lam_a ** int(away_goals)) / math.factorial(int(away_goals))
    return float(p_h * p_a)


def _target_realism_band(prob_pct, rank):
    if rank is not None and rank <= 3 and prob_pct >= 4.0:
        return "high"
    if rank is not None and rank <= 8 and prob_pct >= 2.0:
        return "medium"
    if prob_pct >= 0.8:
        return "low"
    return "long_shot"


def _search_reasonable_shift(lambda_home, lambda_away, target_home, target_away):
    base_prob = _score_probability(lambda_home, lambda_away, target_home, target_away)
    target_prob = min(0.25, base_prob + max(0.008, base_prob * 0.35))

    scales = [round(0.72 + (i * 0.02), 2) for i in range(29)]
    best_reaching = None
    best_any = None

    for h_scale in scales:
        for a_scale in scales:
            cand_home = max(0.25, min(3.8, float(lambda_home) * h_scale))
            cand_away = max(0.25, min(3.8, float(lambda_away) * a_scale))
            prob = _score_probability(cand_home, cand_away, target_home, target_away)
            move = abs(h_scale - 1.0) + abs(a_scale - 1.0)
            candidate = {
                "lambda_home": float(cand_home),
                "lambda_away": float(cand_away),
                "home_scale": float(h_scale),
                "away_scale": float(a_scale),
                "probability": float(prob),
                "move": float(move),
            }

            if best_any is None:
                best_any = candidate
            else:
                best_prob = best_any["probability"]
                if prob > best_prob + 1e-12 or (abs(prob - best_prob) <= 1e-12 and move < best_any["move"]):
                    best_any = candidate

            if prob + 1e-12 < target_prob:
                continue
            if best_reaching is None:
                best_reaching = candidate
            else:
                if move < best_reaching["move"] - 1e-12 or (
                    abs(move - best_reaching["move"]) <= 1e-12
                    and prob > best_reaching["probability"] + 1e-12
                ):
                    best_reaching = candidate

    chosen = best_reaching or best_any or {
        "lambda_home": float(lambda_home),
        "lambda_away": float(lambda_away),
        "home_scale": 1.0,
        "away_scale": 1.0,
        "probability": float(base_prob),
        "move": 0.0,
    }
    chosen["target_probability"] = float(target_prob)
    chosen["target_reached"] = bool(best_reaching)
    return chosen


def _build_target_hypotheses(home, away, target_home, target_away, lambda_home, lambda_away, shift_data, sim):
    home_req = shift_data["lambda_home"]
    away_req = shift_data["lambda_away"]
    home_delta = home_req - float(lambda_home)
    away_delta = away_req - float(lambda_away)
    home_delta_pct = (home_delta / max(0.01, float(lambda_home))) * 100.0
    away_delta_pct = (away_delta / max(0.01, float(lambda_away))) * 100.0

    notes = []
    if home_delta_pct >= 4.0:
        notes.append(
            f"{home} needs about +{home_delta_pct:.1f}% attacking output (+{home_delta:.2f} xG) from cleaner final-third creation and better shot quality."
        )
    elif home_delta_pct <= -4.0:
        notes.append(
            f"{home} should accept a lower-volume attack ({home_delta_pct:.1f}% xG) and prioritize game control once leading."
        )

    if away_delta_pct >= 4.0:
        notes.append(
            f"{away} needs about +{away_delta_pct:.1f}% attacking output (+{away_delta:.2f} xG), likely requiring transition chances and set-piece efficiency."
        )
    elif away_delta_pct <= -4.0:
        notes.append(
            f"{away} must be limited to about {away_delta_pct:.1f}% below current attacking expectation through compact rest-defense and fewer central entries."
        )

    target_result = _result_from_score(f"{target_home}-{target_away}")
    if target_result == "Home":
        notes.append(f"Game-state requirement: {home} should score first to force {away} to open up.")
    elif target_result == "Away":
        notes.append(f"Game-state requirement: {away} should score first so the match shifts toward their preferred transition profile.")
    else:
        notes.append("Game-state requirement: both teams must avoid late risk and keep chance quality moderate after 60'.")

    progression = sim.get("progression_context", {}) if isinstance(sim, dict) else {}
    home_prog_adj = _safe_float((progression or {}).get("home_adjustment"), 0.0) or 0.0
    away_prog_adj = _safe_float((progression or {}).get("away_adjustment"), 0.0) or 0.0
    if home_delta_pct > 4.0 and home_prog_adj < 0:
        notes.append(
            f"{home} currently has negative progression adjustment ({home_prog_adj * 100:.1f}%), so they need to improve vertical progression to hit the target score."
        )
    if away_delta_pct > 4.0 and away_prog_adj < 0:
        notes.append(
            f"{away} currently has negative progression adjustment ({away_prog_adj * 100:.1f}%), so direct attacks must be sharper than baseline."
        )

    fatigue = sim.get("fatigue_context", {}) if isinstance(sim, dict) else {}
    home_fatigue = _safe_float((fatigue or {}).get("home_attack_penalty"), 0.0) or 0.0
    away_fatigue = _safe_float((fatigue or {}).get("away_attack_penalty"), 0.0) or 0.0
    if home_delta_pct > 4.0 and home_fatigue > 0.01:
        notes.append(f"{home} also needs to offset current fatigue penalty ({home_fatigue * 100:.1f}%) by maintaining intensity across both halves.")
    if away_delta_pct > 4.0 and away_fatigue > 0.01:
        notes.append(f"{away} also needs to offset current fatigue penalty ({away_fatigue * 100:.1f}%) to sustain chance creation.")

    key_matchups = sim.get("key_matchups", []) if isinstance(sim, dict) else []
    if key_matchups:
        notes.append(f"Key duel swing to watch: {key_matchups[0]}")

    unique = []
    seen = set()
    for item in notes:
        s = str(item).strip()
        if s and s not in seen:
            seen.add(s)
            unique.append(s)
    return unique[:5]


def analyze_target_score_scenario(home, away, sim, target_score, max_goals=10):
    parsed = _parse_score_pair(target_score)
    if parsed is None:
        return {
            "error": "invalid_target_score",
            "input": target_score,
            "expected_format": "H-A",
        }

    target_home, target_away = parsed
    lambda_home = float((sim or {}).get("expected_goals_home", 1.5))
    lambda_away = float((sim or {}).get("expected_goals_away", 1.2))

    grid_goals = max(int(max_goals), target_home + 6, target_away + 6, 12)
    matrix = _build_poisson_matrix(lambda_home, lambda_away, max_goals=grid_goals)

    rows = []
    for h in range(grid_goals):
        for a in range(grid_goals):
            rows.append((h, a, matrix[h][a]))
    rows.sort(key=lambda x: x[2], reverse=True)

    rank = None
    for idx, (h, a, _) in enumerate(rows, start=1):
        if h == target_home and a == target_away:
            rank = idx
            break

    current_prob = _score_probability(lambda_home, lambda_away, target_home, target_away)
    realism_band = _target_realism_band(current_prob * 100.0, rank)
    top5 = [{"score": f"{h}-{a}", "probability": round(float(p) * 100.0, 2)} for h, a, p in rows[:5]]

    shift_data = _search_reasonable_shift(lambda_home, lambda_away, target_home, target_away)
    shifted_home = float(shift_data["lambda_home"])
    shifted_away = float(shift_data["lambda_away"])
    shifted_prob = float(shift_data["probability"])

    xg_shift = {
        "probability_goal": round(float(shift_data["target_probability"]) * 100.0, 2),
        "goal_reached_with_reasonable_shift": bool(shift_data["target_reached"]),
        "probability_after_shift": round(shifted_prob * 100.0, 2),
        "home_xg_current": round(lambda_home, 3),
        "away_xg_current": round(lambda_away, 3),
        "home_xg_required": round(shifted_home, 3),
        "away_xg_required": round(shifted_away, 3),
        "home_xg_change_pct": round(((shifted_home / max(0.01, lambda_home)) - 1.0) * 100.0, 1),
        "away_xg_change_pct": round(((shifted_away / max(0.01, lambda_away)) - 1.0) * 100.0, 1),
    }

    hypotheses = _build_target_hypotheses(
        home=home,
        away=away,
        target_home=target_home,
        target_away=target_away,
        lambda_home=lambda_home,
        lambda_away=lambda_away,
        shift_data=shift_data,
        sim=sim,
    )

    return {
        "target_score": f"{target_home}-{target_away}",
        "target_result": _result_from_score(f"{target_home}-{target_away}"),
        "current_probability": round(current_prob * 100.0, 2),
        "rank_in_score_grid": int(rank) if rank is not None else None,
        "realism_band": realism_band,
        "top5_scores_now": top5,
        "xg_shift_scenario": xg_shift,
        "hypotheses": hypotheses,
        "assumptions": [
            "Uses current expected-goal surface from the active model output.",
            "Search is constrained to roughly +/-28% xG shift per side to keep scenarios realistic.",
            "Hypotheses are tactical interpretations of xG shift, not guaranteed outcomes.",
        ],
    }


def _pick_result_from_probs(home_prob, draw_prob, away_prob):
    if home_prob > away_prob and home_prob > draw_prob:
        return "Home"
    if away_prob > home_prob and away_prob > draw_prob:
        return "Away"
    return "Draw"


def _pick_score_for_result(lambda_home, lambda_away, result, max_goals=10):
    matrix = _build_poisson_matrix(lambda_home, lambda_away, max_goals=max_goals)

    def ok(h, a):
        if result == "Home":
            return h > a
        if result == "Away":
            return h < a
        return h == a

    best_score, best_prob = None, -1.0
    for h in range(max_goals):
        for a in range(max_goals):
            if not ok(h, a):
                continue
            p = matrix[h][a]
            if p > best_prob:
                best_prob = p
                best_score = f"{h}-{a}"

    if best_score is None:
        for h in range(max_goals):
            for a in range(max_goals):
                p = matrix[h][a]
                if p > best_prob:
                    best_prob = p
                    best_score = f"{h}-{a}"
    return best_score, float(best_prob)

def _poisson_summary(lambda_home, lambda_away, max_goals=10):
    matrix = _build_poisson_matrix(lambda_home, lambda_away, max_goals=max_goals)
    home_win = draw = away_win = 0.0
    rows = []
    for h in range(max_goals):
        for a in range(max_goals):
            p = matrix[h][a]
            rows.append((h, a, p))
            if h > a:
                home_win += p
            elif h == a:
                draw += p
            else:
                away_win += p
    rows.sort(key=lambda x: x[2], reverse=True)
    top3 = rows[:3]
    return {
        "home_win_prob": home_win * 100.0,
        "draw_prob": draw * 100.0,
        "away_win_prob": away_win * 100.0,
        "expected_goals_home": float(lambda_home),
        "expected_goals_away": float(lambda_away),
        "most_likely_score": f"{top3[0][0]}-{top3[0][1]}",
        "top3_scores": ", ".join([f"{h}-{a} ({p * 100:.1f}%)" for h, a, p in top3]),
        "bonus_applied": "Poisson fallback",
        "model_version": "poisson_fallback",
    }


def _calculate_bet_data(lambda_home, lambda_away, max_goals=10):
    matrix = _build_poisson_matrix(lambda_home, lambda_away, max_goals=max_goals)

    def hdp_outcomes(hdp):
        win = push = loss = 0.0
        for h in range(max_goals):
            for a in range(max_goals):
                adj = (h - a) + hdp
                p = matrix[h][a]
                if adj > 0:
                    win += p
                elif adj < 0:
                    loss += p
                else:
                    push += p
        return win, push, loss

    def ou_prob(boundary, side):
        p = 0.0
        for h in range(max_goals):
            for a in range(max_goals):
                total = h + a
                if side == "Over" and total > boundary:
                    p += matrix[h][a]
                if side == "Under" and total < boundary:
                    p += matrix[h][a]
        return p

    bet_data = {}
    bet_detail = {}
    for hdp in [-3, -2, -1, 0, 1, 2, 3]:
        win, push, loss = hdp_outcomes(hdp)
        bet_data[f"HDP_{hdp}"] = win
        bet_detail[f"HDP_{hdp}"] = {"win": win, "push": push, "loss": loss}

    for boundary in [0.5, 1.5, 2.5, 3.5]:
        bet_data[f"Over_{boundary}"] = ou_prob(boundary, "Over")
        bet_data[f"Under_{boundary}"] = ou_prob(boundary, "Under")

    return bet_data, bet_detail


def _safe_float(value, default=None):
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        return default


def _fmt_num(value, digits=2):
    num = _safe_float(value, None)
    if num is None:
        return "N/A"
    return f"{num:.{digits}f}"


def _fmt_pct(value, digits=1):
    num = _safe_float(value, None)
    if num is None:
        return "N/A"
    return f"{num:.{digits}f}%"


def _clamp01(value):
    return max(0.0, min(1.0, float(value)))


def _extract_player_label(items):
    if not items:
        return None
    raw = str(items[0]).strip()
    if not raw:
        return None
    return raw.split("(", 1)[0].strip()


def _norm_share(value, scale):
    return float(math.tanh(max(0.0, float(value)) / max(1e-9, float(scale))))


def _team_scenario_inputs(team_name, lambda_for, flow_team, flow_opp, squad_team, prog_team):
    ppda_team = _safe_float(_pick_first(flow_team, ["calc_PPDA", "PPDA"]), 8.0)
    ppda_opp = _safe_float(_pick_first(flow_opp, ["calc_PPDA", "PPDA"]), 8.0)
    field_tilt = _safe_float(_pick_first(flow_team, ["calc_FieldTilt_Pct"]), 0.5)
    if field_tilt is not None and field_tilt > 1.5:
        field_tilt = field_tilt / 100.0
    field_tilt = _clamp01(field_tilt if field_tilt is not None else 0.5)
    high_error_rate = _safe_float(_pick_first(flow_team, ["calc_HighError_Rate"]), 12.0)
    directness = _safe_float(_pick_first(flow_team, ["calc_Directness"]), 0.08)
    big_chance_diff = _safe_float(_pick_first(flow_team, ["calc_BigChance_Diff"]), 0.0)

    possession = _safe_float(_pick_first(squad_team, ["Poss", "averageBallPossession", "Possession"]), 50.0)
    if possession is not None and possession <= 1.5:
        possession = possession * 100.0

    xt_proxy = _safe_float((prog_team or {}).get("xt_proxy"), 0.45)
    counter_index = _safe_float((prog_team or {}).get("counter_punch_index"), 0.25)
    u_shape_risk = _safe_float((prog_team or {}).get("u_shape_risk"), 0.35)
    deep_completion = _safe_float((prog_team or {}).get("deep_completion_proxy"), 3.0)
    progressive_carry = _safe_float((prog_team or {}).get("prg_carry_dist"), 4.5)
    big_created_p90 = _safe_float((prog_team or {}).get("big_created_p90"), 1.6)
    inside_box_shots_p90 = _safe_float((prog_team or {}).get("inside_box_shots_p90"), 4.5)
    fast_breaks_p90 = _safe_float((prog_team or {}).get("fast_breaks_p90"), 1.2)
    corners_p90 = _safe_float((prog_team or {}).get("corners_p90"), 4.5)
    long_balls_p90 = _safe_float((prog_team or {}).get("long_balls_p90"), 28.0)
    shots_on_target_p90 = _safe_float((prog_team or {}).get("shots_on_target_p90"), 3.2)

    pressing_edge = _clamp01((ppda_opp - ppda_team) / max(2.5, ppda_opp))
    forced_error_norm = _norm_share(high_error_rate, 22.0)
    directness_norm = _clamp01(directness / 0.18)
    possession_norm = _clamp01((possession or 50.0) / 100.0)
    deep_norm = _norm_share(deep_completion, 5.5)
    carry_norm = _norm_share(progressive_carry, 7.5)
    big_created_norm = _norm_share(big_created_p90, 2.5)
    inside_box_norm = _norm_share(inside_box_shots_p90, 6.0)
    fast_break_norm = _norm_share(fast_breaks_p90, 2.8)
    corners_norm = _norm_share(corners_p90, 5.0)
    long_ball_norm = _norm_share(long_balls_p90, 34.0)
    sot_norm = _norm_share(shots_on_target_p90, 4.0)
    score_prob = 1.0 - math.exp(-max(0.0, float(lambda_for)))

    return {
        "team": team_name,
        "lambda_for": float(lambda_for),
        "score_prob": float(score_prob),
        "ppda_team": float(ppda_team),
        "ppda_opp": float(ppda_opp),
        "field_tilt": float(field_tilt),
        "high_error_rate": float(high_error_rate),
        "directness": float(directness),
        "big_chance_diff": float(big_chance_diff),
        "possession": float(possession if possession is not None else 50.0),
        "xt_proxy": float(xt_proxy),
        "counter_index": float(counter_index),
        "u_shape_risk": float(u_shape_risk),
        "deep_completion": float(deep_completion),
        "progressive_carry": float(progressive_carry),
        "big_created_p90": float(big_created_p90),
        "inside_box_shots_p90": float(inside_box_shots_p90),
        "fast_breaks_p90": float(fast_breaks_p90),
        "corners_p90": float(corners_p90),
        "long_balls_p90": float(long_balls_p90),
        "shots_on_target_p90": float(shots_on_target_p90),
        "pressing_edge": float(pressing_edge),
        "forced_error_norm": float(forced_error_norm),
        "directness_norm": float(directness_norm),
        "possession_norm": float(possession_norm),
        "deep_norm": float(deep_norm),
        "carry_norm": float(carry_norm),
        "big_created_norm": float(big_created_norm),
        "inside_box_norm": float(inside_box_norm),
        "fast_break_norm": float(fast_break_norm),
        "corners_norm": float(corners_norm),
        "long_ball_norm": float(long_ball_norm),
        "sot_norm": float(sot_norm),
    }


def _scenario_confidence(input_data):
    checks = [
        input_data.get("ppda_team"),
        input_data.get("ppda_opp"),
        input_data.get("field_tilt"),
        input_data.get("xt_proxy"),
        input_data.get("counter_index"),
        input_data.get("deep_completion"),
        input_data.get("corners_p90"),
        input_data.get("long_balls_p90"),
    ]
    available = sum(1 for x in checks if x is not None)
    ratio = available / max(1, len(checks))
    if ratio >= 0.85:
        return "high"
    if ratio >= 0.60:
        return "medium"
    return "low"


def _build_team_tactical_scenarios(team_inputs, opp_inputs, creator_name=None):
    t = team_inputs
    o = opp_inputs
    confidence = _scenario_confidence(t)
    creator = creator_name or "เพลย์เมกเกอร์"

    # Scenario A: High press -> fast recognition -> long/high release to free winger.
    event_a = _clamp01(
        0.10
        + (0.27 * t["pressing_edge"])
        + (0.17 * t["forced_error_norm"])
        + (0.12 * t["counter_index"])
        + (0.10 * t["directness_norm"])
        + (0.08 * t["field_tilt"])
    )
    conv_a = _clamp01(
        0.09
        + (0.13 * t["deep_norm"])
        + (0.12 * t["score_prob"])
        + (0.07 * t["big_created_norm"])
        + (0.04 * t["carry_norm"])
    )
    goal_a = event_a * conv_a

    # Scenario B: Absorb pressure -> counter attack into weak-side channel.
    transition_window = _clamp01((o["field_tilt"] - t["field_tilt"]) + 0.22)
    event_b = _clamp01(
        0.08
        + (0.30 * t["counter_index"])
        + (0.15 * t["fast_break_norm"])
        + (0.10 * t["directness_norm"])
        + (0.10 * transition_window)
    )
    conv_b = _clamp01(
        0.08
        + (0.15 * t["score_prob"])
        + (0.08 * t["inside_box_norm"])
        + (0.06 * t["carry_norm"])
        + (0.05 * t["sot_norm"])
    )
    goal_b = event_b * conv_b

    # Scenario C: Sustained territory -> set-piece/second-ball shot.
    set_piece_base = _clamp01((t["field_tilt"] * 0.8) + (t["possession_norm"] * 0.2))
    event_c = _clamp01(
        0.07
        + (0.22 * t["corners_norm"])
        + (0.12 * set_piece_base)
        + (0.10 * t["inside_box_norm"])
        + (0.06 * max(0.0, (t["big_chance_diff"] + 10.0) / 25.0))
    )
    conv_c = _clamp01(
        0.07
        + (0.11 * t["score_prob"])
        + (0.08 * t["big_created_norm"])
        + (0.05 * t["forced_error_norm"])
    )
    goal_c = event_c * conv_c

    scenarios = [
        {
            "team": t["team"],
            "scenario_code": "press_to_wide_release",
            "scenario": "กดดันสูงแล้วแทงบอลยาวหนีไลน์ให้ตัวรุกริมเส้นเข้าเขตอันตราย",
            "probability_pct": round(event_a * 100.0, 2),
            "goal_probability_pct": round(goal_a * 100.0, 2),
            "confidence": confidence,
            "sequence": [
                f"{t['team']} บีบด้วย PPDA {t['ppda_team']:.2f} เทียบคู่แข่ง {t['ppda_opp']:.2f}",
                f"{creator} อ่านจังหวะแล้วเห็นตัวรุกยืนว่างริมเส้น",
                "เล่นบอลสูง/บอลวางข้ามแนวรับเข้า half-space เพื่อตัดหลังไลน์",
                "ตัวรุกแตะบอลแรกเข้าพื้นที่อันตรายและสร้างโอกาสยิงทันที",
            ],
            "statistical_basis": {
                "ppda_team": round(t["ppda_team"], 3),
                "ppda_opponent": round(t["ppda_opp"], 3),
                "high_error_rate": round(t["high_error_rate"], 3),
                "directness": round(t["directness"], 4),
                "xt_proxy": round(t["xt_proxy"], 3),
                "counter_punch_index": round(t["counter_index"], 3),
                "long_balls_p90": round(t["long_balls_p90"], 2),
                "expected_goals_team": round(t["lambda_for"], 3),
            },
        },
        {
            "team": t["team"],
            "scenario_code": "counter_after_absorb",
            "scenario": "ถอยรับแล้วสวนกลับเร็วเข้าช่องกว้างฝั่งอ่อน",
            "probability_pct": round(event_b * 100.0, 2),
            "goal_probability_pct": round(goal_b * 100.0, 2),
            "confidence": confidence,
            "sequence": [
                f"{t['team']} ปล่อยคู่แข่งครองบอลช่วงสั้นแล้วดักจังหวะเปลี่ยนเกม",
                "จ่ายบอลแรกทะลุช่องหรือออกริมเส้นเพื่อชิงความได้เปรียบเชิงพื้นที่",
                "เร่งเข้าเขตโทษใน 2-3 จังหวะ พร้อมจบจาก inside-box",
            ],
            "statistical_basis": {
                "counter_punch_index": round(t["counter_index"], 3),
                "fast_breaks_p90": round(t["fast_breaks_p90"], 2),
                "field_tilt_team": round(t["field_tilt"], 3),
                "field_tilt_opponent": round(o["field_tilt"], 3),
                "inside_box_shots_p90": round(t["inside_box_shots_p90"], 2),
                "expected_goals_team": round(t["lambda_for"], 3),
            },
        },
        {
            "team": t["team"],
            "scenario_code": "set_piece_second_ball",
            "scenario": "กดพื้นที่ต่อเนื่องแล้วจบจากลูกตั้งเตะ/จังหวะเก็บตก",
            "probability_pct": round(event_c * 100.0, 2),
            "goal_probability_pct": round(goal_c * 100.0, 2),
            "confidence": confidence,
            "sequence": [
                f"{t['team']} ขยับเกมบุกจนได้ corner/free-kick ต่อเนื่อง",
                "โจมตีจุดตกบอลแรกและเก็บบอลสองหน้ากรอบเพื่อยิงซ้ำ",
                "หากบล็อกไม่ทัน มีโอกาสได้ shot on target จากจังหวะสอง",
            ],
            "statistical_basis": {
                "corners_p90": round(t["corners_p90"], 2),
                "field_tilt": round(t["field_tilt"], 3),
                "inside_box_shots_p90": round(t["inside_box_shots_p90"], 2),
                "big_created_p90": round(t["big_created_p90"], 2),
                "expected_goals_team": round(t["lambda_for"], 3),
            },
        },
    ]
    return scenarios


def build_tactical_scenario_report(
    home_team,
    away_team,
    sim,
    home_flow,
    away_flow,
    home_squad,
    away_squad,
    home_prog,
    away_prog,
    home_top_rated,
    away_top_rated,
    max_scenarios=6,
):
    lambda_home = _safe_float((sim or {}).get("expected_goals_home"), 1.35)
    lambda_away = _safe_float((sim or {}).get("expected_goals_away"), 1.20)

    home_inputs = _team_scenario_inputs(home_team, lambda_home, home_flow, away_flow, home_squad, home_prog)
    away_inputs = _team_scenario_inputs(away_team, lambda_away, away_flow, home_flow, away_squad, away_prog)

    home_creator = _extract_player_label(home_top_rated)
    away_creator = _extract_player_label(away_top_rated)

    scenarios = []
    scenarios.extend(_build_team_tactical_scenarios(home_inputs, away_inputs, creator_name=home_creator))
    scenarios.extend(_build_team_tactical_scenarios(away_inputs, home_inputs, creator_name=away_creator))
    scenarios.sort(key=lambda x: (x.get("goal_probability_pct", 0.0), x.get("probability_pct", 0.0)), reverse=True)
    scenarios = scenarios[: max(1, int(max_scenarios))]

    for i, sc in enumerate(scenarios, start=1):
        sc["rank"] = i
        if sc.get("goal_probability_pct", 0.0) >= 10.0:
            sc["impact_tier"] = "high"
        elif sc.get("goal_probability_pct", 0.0) >= 6.0:
            sc["impact_tier"] = "medium"
        else:
            sc["impact_tier"] = "low"

    return {
        "method": "heuristic_event_model_v1",
        "description": "Event probabilities estimated from PPDA, field tilt, progression proxies, and expected-goal surface.",
        "match": f"{home_team} vs {away_team}",
        "model_expected_goals": {
            "home": round(float(lambda_home), 3),
            "away": round(float(lambda_away), 3),
        },
        "scenarios": scenarios,
        "notes": [
            "probability_pct = chance that this tactical pattern occurs at least once in the match.",
            "goal_probability_pct = chance that the same tactical pattern leads to at least one goal.",
            "These are statistically-guided scenario probabilities, not guaranteed outcomes.",
        ],
    }


def _pick_first(row, columns, default=None):
    if row is None:
        return default
    for col in columns:
        if col in row and pd.notna(row.get(col)):
            return row.get(col)
    return default


def get_game_flow_stats(team_name, league):
    file_path = Path("game flow") / f"{league}_GameFlow.xlsx"
    if not file_path.exists():
        return {}
    try:
        df = pd.read_excel(file_path)
        for col in ["Team_Name", "Team", "Squad"]:
            row = _find_team_row(df, col, team_name)
            if row is not None:
                return row.to_dict()
    except Exception:
        pass
    return {}


def get_squad_stats(team_name, league):
    file_path = Path("all stats") / f"{league}_Stats.xlsx"
    if not file_path.exists():
        return {}
    try:
        df = pd.read_excel(file_path)
        for col in ["Squad", "Team_Name", "Team"]:
            row = _find_team_row(df, col, team_name)
            if row is not None:
                return row.to_dict()
    except Exception:
        pass
    return {}


def _find_player_stats_file(team_name, league):
    base = Path("sofaplayer") / league
    if not base.exists():
        return None
    aliases = [_normalize_text(a) for a in _team_aliases(team_name)]
    for file_path in base.glob("*_stats.xlsx"):
        stem = _normalize_text(file_path.stem.replace("_stats", ""))
        if any(alias and (alias == stem or alias in stem or stem in alias) for alias in aliases):
            return file_path
    return None


def get_top_players(team_name, league, top_n=3):
    file_path = _find_player_stats_file(team_name, league)
    if file_path is None:
        return [], []

    try:
        df = pd.read_excel(file_path)
    except Exception:
        return [], []
    if df.empty:
        return [], []

    name_col = next((c for c in ["Player_Name", "Player", "Name"] if c in df.columns), None)
    if not name_col:
        return [], []

    rating_col = next((c for c in ["rating", "Rating", "avgRating"] if c in df.columns), None)
    goals_col = next((c for c in ["goals", "Goals", "Gls"] if c in df.columns), None)

    top_rated = df.copy()
    if rating_col:
        top_rated[rating_col] = pd.to_numeric(top_rated[rating_col], errors="coerce")
        top_rated = top_rated.sort_values(rating_col, ascending=False, na_position="last")
    top_rated = top_rated.head(top_n)

    rated_out = []
    for _, row in top_rated.iterrows():
        player_name = str(row.get(name_col, "")).strip()
        if not player_name:
            continue
        if rating_col:
            rating_value = _safe_float(row.get(rating_col), None)
            rated_out.append(f"{player_name} (Rating {rating_value:.2f})" if rating_value is not None else player_name)
        else:
            rated_out.append(player_name)

    scorer_out = []
    if goals_col:
        top_goal = df.copy()
        top_goal[goals_col] = pd.to_numeric(top_goal[goals_col], errors="coerce")
        top_goal = top_goal.sort_values(goals_col, ascending=False, na_position="last").head(top_n)
        for _, row in top_goal.iterrows():
            player_name = str(row.get(name_col, "")).strip()
            if not player_name:
                continue
            goals_value = _safe_float(row.get(goals_col), None)
            scorer_out.append(f"{player_name} ({int(goals_value)} goals)" if goals_value is not None else player_name)

    return rated_out, scorer_out


def _load_gemini_api_key():
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key, "env:GEMINI_API_KEY"

    key_file = Path("gemini_key.txt")
    if not key_file.exists():
        return None, None

    try:
        raw = key_file.read_text(encoding="utf-8")
    except Exception:
        return None, None

    for line in raw.splitlines():
        cleaned = line.strip().strip('"').strip("'")
        if not cleaned or cleaned.startswith("#"):
            continue
        if "=" in cleaned:
            cleaned = cleaned.split("=", 1)[1].strip().strip('"').strip("'")
        if cleaned:
            return cleaned, "file:gemini_key.txt"
    return None, None


def _extract_gemini_text(response_json):
    candidates = response_json.get("candidates") if isinstance(response_json, dict) else None
    if not candidates:
        return None
    for cand in candidates:
        content = cand.get("content", {}) if isinstance(cand, dict) else {}
        parts = content.get("parts", [])
        texts = []
        for part in parts:
            if isinstance(part, dict):
                text = part.get("text")
                if text:
                    texts.append(str(text))
        if texts:
            return "\n".join(texts).strip()
    return None


def _build_gemini_prompt(
    home,
    away,
    league,
    sim,
    result_1x2,
    score_aligned,
    result_from_score,
    qc_flags,
    context_text,
    home_flow,
    away_flow,
    home_squad,
    away_squad,
    home_top_rated,
    away_top_rated,
    home_top_scorers,
    away_top_scorers,
):
    home_ppda = _pick_first(home_flow, ["calc_PPDA", "PPDA"])
    away_ppda = _pick_first(away_flow, ["calc_PPDA", "PPDA"])
    home_poss = _pick_first(home_squad, ["Poss", "averageBallPossession", "Possession"])
    away_poss = _pick_first(away_squad, ["Poss", "averageBallPossession", "Possession"])
    home_g90 = _pick_first(home_squad, ["Per 90 Minutes_Gls", "goalsScored_per_90", "Goals/90"])
    away_g90 = _pick_first(away_squad, ["Per 90 Minutes_Gls", "goalsScored_per_90", "Goals/90"])
    home_ga90 = _pick_first(home_squad, ["Per 90 Minutes_GA", "goalsConceded_per_90", "GA/90"])
    away_ga90 = _pick_first(away_squad, ["Per 90 Minutes_GA", "goalsConceded_per_90", "GA/90"])

    qc_text = " | ".join(qc_flags) if qc_flags else "No critical QC flags"
    home_rated_text = ", ".join(home_top_rated) if home_top_rated else "N/A"
    away_rated_text = ", ".join(away_top_rated) if away_top_rated else "N/A"
    home_scorer_text = ", ".join(home_top_scorers) if home_top_scorers else "N/A"
    away_scorer_text = ", ".join(away_top_scorers) if away_top_scorers else "N/A"

    return f"""
คุณคือนักวิเคราะห์ฟุตบอลอาชีพที่มีประสบการณ์สูง ให้เขียนรายงานภาษาไทยเชิงลึกแบบมืออาชีพในรูปแบบ Markdown
สำหรับเกม **{home} vs {away}** และใช้ข้อมูลด้านล่างเท่านั้น

ข้อมูลที่ยืนยันแล้ว (Verified Data)
- Match: {home} vs {away}
- League: {league}
- Model Version: {sim.get('model_version', 'v9')}
- Home Win: {_fmt_pct(sim.get('home_win_prob'))}
- Draw: {_fmt_pct(sim.get('draw_prob'))}
- Away Win: {_fmt_pct(sim.get('away_win_prob'))}
- Predicted 1X2: {result_1x2}
- Predicted Score (aligned): {home} {score_aligned} {away}
- Predicted Result from Score: {result_from_score}
- Expected Goals: {home} {_fmt_num(sim.get('expected_goals_home'))} | {away} {_fmt_num(sim.get('expected_goals_away'))}
- Top 3 Scores: {sim.get('top3_scores', 'N/A')}
- Data QC Flags: {qc_text}

Team Style Snapshot
- {home}: PPDA={_fmt_num(home_ppda)}, Possession={_fmt_pct(home_poss)}, Goals/90={_fmt_num(home_g90)}, Conceded/90={_fmt_num(home_ga90)}
- {away}: PPDA={_fmt_num(away_ppda)}, Possession={_fmt_pct(away_poss)}, Goals/90={_fmt_num(away_g90)}, Conceded/90={_fmt_num(away_ga90)}
- Key Rated ({home}): {home_rated_text}
- Key Rated ({away}): {away_rated_text}
- Top Scorers ({home}): {home_scorer_text}
- Top Scorers ({away}): {away_scorer_text}

Live Context / Team News
{context_text}

ข้อกำหนดรูปแบบ (ต้องทำตาม)
1) เปิดรายงานด้วยย่อหน้าเกริ่น 1 ย่อหน้า แล้วคั่นด้วย ---
2) ต้องมีหัวข้อหลัก 2 ส่วนดังนี้:
# **ส่วนที่ 1: การวิเคราะห์ภาพรวมทีม (Team Overview Analysis)**
และ
# **ส่วนที่ 2: การวิเคราะห์ผู้เล่นรายบุคคล (Player Analysis)**
3) ส่วนที่ 1 ต้องมีหัวข้อย่อย:
- สภาพทีม & ข่าวล่าสุด
- การวิเคราะห์เชิงกลยุทธ์ & แทคติก
- ตารางเปรียบเทียบกลยุทธ์ (ต้องเป็นตาราง Markdown)
- ภาพรวมและแนวโน้ม
- บทสรุปภาพรวม (ต้องฟันธงสกอร์และความมั่นใจ สูง/กลาง/ต่ำ)
4) ส่วนที่ 2 ต้องมีหัวข้อย่อย:
- เจาะลึกผู้เล่นหลัก
- ดวลกันตัวต่อตัว
- ตัวทีเด็ด (X-Factor)
5) ใช้โทนมืออาชีพ ชัดเจน มีเหตุผล ไม่เวอร์เกินข้อมูล
6) ห้ามแต่งสถิติที่ไม่มีในอินพุต ถ้าข้อมูลไม่พอให้เขียนว่า "ข้อมูลไม่พอ"
7) ปิดท้ายด้วยบรรทัด "รายงานโดย: AI Analyst Systems"
"""


def _generate_ai_report(prompt, api_key, model="gemini-2.0-flash", max_retries=3, timeout_sec=90):
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "topP": 0.95},
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            response = requests.post(
                api_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=timeout_sec,
            )
        except Exception as ex:
            last_error = f"request_failed: {ex}"
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None, last_error

        if response.status_code == 200:
            try:
                data = response.json()
            except Exception:
                return None, "invalid_json_from_gemini"
            text = _extract_gemini_text(data)
            if text:
                return text, None
            return None, "gemini_returned_no_text"

        body = response.text.strip().replace("\n", " ")
        if len(body) > 240:
            body = body[:240] + "..."
        last_error = f"gemini_http_{response.status_code}: {body}"
        if response.status_code in {429, 500, 502, 503, 504} and attempt < max_retries - 1:
            time.sleep(2 ** attempt)
            continue
        return None, last_error

    return None, last_error or "unknown_gemini_error"


def _try_simulator(home, away, league, home_sim_stats, away_sim_stats, home_prog, away_prog, context_text):
    try:
        import xg_engine
        import simulator_v9

        eng = xg_engine.XGEngine(league)
        h_xg = eng.get_team_rolling_stats(home, n_games=10)
        a_xg = eng.get_team_rolling_stats(away, n_games=10)
        if not (h_xg and a_xg):
            raise RuntimeError("xG data missing")
        return simulator_v9.simulate_match(
            h_xg,
            a_xg,
            home_sim_stats,
            away_sim_stats,
            iterations=10000,
            league=league,
            home_team=home,
            away_team=away,
            context_text=context_text,
            home_progression=home_prog,
            away_progression=away_prog,
        )
    except Exception as ex:
        print(f"[Warning] simulator_v9 unavailable, fallback Poisson: {ex}")
        l_home = float((home_sim_stats or {}).get("goals_scored_per_game", 1.45))
        l_away = float((away_sim_stats or {}).get("goals_scored_per_game", 1.25))
        return _poisson_summary(l_home, l_away)


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Analyze a football match and export prediction JSON.")
    parser.add_argument("home_team", help="Home team name")
    parser.add_argument("away_team", help="Away team name")
    parser.add_argument(
        "--target-score",
        dest="target_score",
        help="Optional desired score in H-A format (example: 2-1)",
    )
    return parser.parse_args(argv)


def main():
    args = _parse_args(sys.argv[1:])

    home = args.home_team.strip()
    away = args.away_team.strip()
    print(f"Analyzing {home} vs {away} ...")

    home_league = find_team_league(home)
    away_league = find_team_league(away)
    league = home_league or away_league or "Premier_League"

    if home_league and away_league and home_league != away_league:
        print(f"[Warning] League mismatch: home={home_league}, away={away_league}. Using {league}.")

    home_sim_stats = get_simulation_stats(home, league)
    away_sim_stats = get_simulation_stats(away, league)
    home_prog = get_progression_stats(home, league)
    away_prog = get_progression_stats(away, league)

    context_text = _load_live_context("match_context.txt")
    qc_flags, context_header = run_data_qc(home, away, league, context_text, home_league, away_league)

    sim = _try_simulator(home, away, league, home_sim_stats, away_sim_stats, home_prog, away_prog, context_text)

    result_1x2 = _pick_result_from_probs(sim["home_win_prob"], sim["draw_prob"], sim["away_win_prob"])
    score_unconditional = sim.get("most_likely_score", "1-1")
    score_aligned, aligned_prob = _pick_score_for_result(
        sim.get("expected_goals_home", 1.5),
        sim.get("expected_goals_away", 1.2),
        result_1x2,
        max_goals=10,
    )
    result_from_score = _result_from_score(score_aligned)
    final_result = result_from_score or result_1x2

    target_score_analysis = None
    if args.target_score:
        target_score_analysis = analyze_target_score_scenario(
            home=home,
            away=away,
            sim=sim,
            target_score=args.target_score,
            max_goals=10,
        )
        if target_score_analysis.get("error"):
            print(f"[Warning] Target score input '{args.target_score}' is invalid. Use H-A format (example: 2-1).")
        else:
            print(
                f"[Info] Target score scenario for {target_score_analysis['target_score']}: "
                f"{target_score_analysis['current_probability']:.2f}% baseline probability."
            )

    home_flow = get_game_flow_stats(home, league)
    away_flow = get_game_flow_stats(away, league)
    home_squad = get_squad_stats(home, league)
    away_squad = get_squad_stats(away, league)
    home_top_rated, home_top_scorers = get_top_players(home, league, top_n=3)
    away_top_rated, away_top_scorers = get_top_players(away, league, top_n=3)
    tactical_scenarios = build_tactical_scenario_report(
        home_team=home,
        away_team=away,
        sim=sim,
        home_flow=home_flow,
        away_flow=away_flow,
        home_squad=home_squad,
        away_squad=away_squad,
        home_prog=home_prog,
        away_prog=away_prog,
        home_top_rated=home_top_rated,
        away_top_rated=away_top_rated,
        max_scenarios=6,
    )

    analysis_file = _analysis_path(home, away)
    analysis_generated = False
    analysis_error = None
    gemini_key_source = None

    gemini_key, gemini_key_source = _load_gemini_api_key()
    if gemini_key:
        prompt = _build_gemini_prompt(
            home=home,
            away=away,
            league=league,
            sim=sim,
            result_1x2=result_1x2,
            score_aligned=score_aligned,
            result_from_score=result_from_score,
            qc_flags=qc_flags,
            context_text=context_text,
            home_flow=home_flow,
            away_flow=away_flow,
            home_squad=home_squad,
            away_squad=away_squad,
            home_top_rated=home_top_rated,
            away_top_rated=away_top_rated,
            home_top_scorers=home_top_scorers,
            away_top_scorers=away_top_scorers,
        )
        ai_report, analysis_error = _generate_ai_report(prompt=prompt, api_key=gemini_key)
        if ai_report:
            os.makedirs("analyses", exist_ok=True)
            with open(analysis_file, "w", encoding="utf-8") as f:
                f.write(ai_report)
            analysis_generated = True
            print(f"[Info] Analysis saved to {analysis_file}")
        else:
            print(f"[Warning] Gemini report generation failed: {analysis_error}")
    else:
        analysis_error = "missing_api_key"
        print(
            "[Info] GEMINI_API_KEY not found. AI report was skipped."
            " Set env var as described in README or add key to gemini_key.txt."
        )

    bet_data, bet_detail = _calculate_bet_data(
        sim.get("expected_goals_home", 1.5),
        sim.get("expected_goals_away", 1.2),
        max_goals=10,
    )

    canonical_home = _canonical_team_name(home)
    canonical_away = _canonical_team_name(away)

    prediction = {
        "Date": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "Match": f"{home} vs {away}",
        "Match_Canonical": f"{canonical_home} vs {canonical_away}",
        "League": league,
        "Home_Team": home,
        "Away_Team": away,
        "Home_Team_Canonical": canonical_home,
        "Away_Team_Canonical": canonical_away,
        "Pred_Home_Win": float(sim["home_win_prob"]),
        "Pred_Draw": float(sim["draw_prob"]),
        "Pred_Away_Win": float(sim["away_win_prob"]),
        "Pred_Score": score_aligned,
        "Pred_Result": final_result,
        "Pred_Score_Unconditional": score_unconditional,
        "Pred_Result_1X2": result_1x2,
        "Pred_Result_From_Score": result_from_score,
        "Pred_Aligned_Score_Prob": float(aligned_prob * 100.0),
        "Expected_Goals_Home": float(sim.get("expected_goals_home", 0.0)),
        "Expected_Goals_Away": float(sim.get("expected_goals_away", 0.0)),
        "Base_Expected_Goals_Home": _safe_float(sim.get("base_exp_home"), None),
        "Base_Expected_Goals_Away": _safe_float(sim.get("base_exp_away"), None),
        "Target_Score_Input": args.target_score,
        "Target_Score_Analysis": target_score_analysis,
        "Model_Version": sim.get("model_version", "unknown"),
        "QC_Flags": qc_flags,
        "Context_Header": context_header,
        "Bet_Data": bet_data,
        "Bet_Detail": bet_detail,
        "Progression_Data": {"home": home_prog, "away": away_prog},
        "Tactical_Scenarios": tactical_scenarios,
        "Calibration_Context": sim.get("calibration_context", {}),
        "AI_Report_Generated": analysis_generated,
        "AI_Report_Path": analysis_file if analysis_generated else None,
        "AI_Report_Error": None if analysis_generated else analysis_error,
        "Gemini_Key_Source": gemini_key_source,
    }

    with open("latest_prediction.json", "w", encoding="utf-8") as f:
        json.dump(prediction, f, indent=4, ensure_ascii=False)

    if not analysis_generated:
        print("[Info] Analysis file was not created (Gemini not available or request failed).")
    print("[Info] Prediction saved to latest_prediction.json")
    print("[Info] Run: python update_tracker.py save")


if __name__ == "__main__":
    main()
