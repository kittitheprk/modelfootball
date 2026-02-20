
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

SOFASCORE_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}
SOFASCORE_CONTEXT_MARKER = "<!-- AUTO_SOFASCORE_LINEUPS -->"
SOFASCORE_POSITION_MAP = {
    "G": "GK",
    "GK": "GK",
    "D": "DEF",
    "DEF": "DEF",
    "M": "MID",
    "MID": "MID",
    "F": "ATT",
    "FW": "ATT",
    "ATT": "ATT",
}


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
    raw_name = str(name).strip()
    items = {raw_name, normalize_team_name(raw_name), _canonical_team_name(raw_name)}
    base_norm = _normalize_text(raw_name)
    for short_name, long_name in TEAM_NAME_MAP.items():
        if _normalize_text(short_name) == base_norm:
            items.add(long_name)
        if _normalize_text(long_name) == base_norm:
            items.add(short_name)
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


def _extract_sofascore_event_id(context_text):
    text = str(context_text or "")
    patterns = [
        r"embed/lineups\?[^#\n]*?\bid=(\d+)",
        r"[?&]id=(\d+)",
        r"#id:(\d+)",
        r"/event/(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _sofascore_get_json(url, timeout_sec=20):
    try:
        response = requests.get(url, headers=SOFASCORE_HTTP_HEADERS, timeout=timeout_sec)
    except Exception as ex:
        return None, f"request_failed: {ex}"
    if response.status_code != 200:
        body = response.text.strip().replace("\n", " ")
        if len(body) > 220:
            body = body[:220] + "..."
        return None, f"http_{response.status_code}: {body}"
    try:
        return response.json(), None
    except Exception:
        return None, "invalid_json"


def _sofascore_player_name(entry):
    if not isinstance(entry, dict):
        return None
    player = entry.get("player", {})
    if isinstance(player, dict):
        name = str(player.get("name") or player.get("shortName") or "").strip()
        if name:
            return name
    fallback = str(entry.get("name") or "").strip()
    return fallback if fallback else None


def _sofascore_position_code(value):
    raw = str(value or "").strip().upper()
    if not raw:
        return ""
    return SOFASCORE_POSITION_MAP.get(raw, raw)


def _sofascore_float(value):
    try:
        out = float(value)
        return out
    except Exception:
        return None


def _sofascore_player_payload(entry):
    if not isinstance(entry, dict):
        return None

    player = entry.get("player", {})
    player = player if isinstance(player, dict) else {}

    name = str(player.get("name") or player.get("shortName") or entry.get("name") or "").strip()
    if not name:
        return None

    position = _sofascore_position_code(entry.get("position") or player.get("position"))
    shirt = str(entry.get("shirtNumber") or entry.get("jerseyNumber") or player.get("jerseyNumber") or "").strip()
    avg_rating = _sofascore_float(entry.get("avgRating"))
    player_id = player.get("id") if player.get("id") is not None else entry.get("playerId")

    return {
        "id": player_id,
        "name": name,
        "position": position,
        "shirt": shirt,
        "avg_rating": avg_rating,
        "substitute": bool(entry.get("substitute")),
    }


def _format_sofascore_player_inline(player_item):
    if not isinstance(player_item, dict):
        return None
    name = str(player_item.get("name") or "").strip()
    if not name:
        return None

    tags = []
    pos = str(player_item.get("position") or "").strip()
    if pos:
        tags.append(pos)
    shirt = str(player_item.get("shirt") or "").strip()
    if shirt:
        tags.append(f"#{shirt}")

    out = name
    if tags:
        out += f" ({' '.join(tags)})"
    return out


def _sofascore_collect_players(items):
    out, seen = [], set()
    for item in items or []:
        payload = _sofascore_player_payload(item)
        if not payload:
            continue

        pid = payload.get("id")
        if pid is not None:
            key = f"id:{pid}"
        else:
            key = f"name:{_normalize_text(payload.get('name'))}"
        if not key or key in seen:
            continue

        seen.add(key)
        out.append(payload)
    return out


def _sofascore_collect_names(items):
    out, seen = [], set()
    for item in items or []:
        name = _sofascore_player_name(item)
        if not name:
            continue
        key = _normalize_text(name)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def _sofascore_collect_side(side_payload):
    if not isinstance(side_payload, dict):
        return [], [], [], "N/A"

    players = _sofascore_collect_players(side_payload.get("players") or [])
    starters = [p for p in players if not bool(p.get("substitute"))]
    bench = [p for p in players if bool(p.get("substitute"))]

    # Fallback for payloads without explicit substitute flags.
    if not starters and players:
        starters = players[:11]
        bench = players[11:]

    missing = _sofascore_collect_players(side_payload.get("missingPlayers") or [])
    formation = str(side_payload.get("formation") or "N/A")
    return starters[:11], bench, missing, formation


def _build_sofascore_context_block(event_id, lineups_json, event_json, home_hint=None, away_hint=None):
    event = (event_json or {}).get("event", {}) if isinstance(event_json, dict) else {}
    event_home = ((event.get("homeTeam") or {}).get("name") if isinstance(event, dict) else None) or None
    event_away = ((event.get("awayTeam") or {}).get("name") if isinstance(event, dict) else None) or None
    home_name = str(home_hint or event_home or "Home Team")
    away_name = str(away_hint or event_away or "Away Team")

    home_start, home_bench, home_missing, home_formation = _sofascore_collect_side((lineups_json or {}).get("home"))
    away_start, away_bench, away_missing, away_formation = _sofascore_collect_side((lineups_json or {}).get("away"))

    home_xi_text = ", ".join([x for x in (_format_sofascore_player_inline(p) for p in home_start) if x]) if home_start else "N/A"
    away_xi_text = ", ".join([x for x in (_format_sofascore_player_inline(p) for p in away_start) if x]) if away_start else "N/A"
    home_bench_text = ", ".join([x for x in (_format_sofascore_player_inline(p) for p in home_bench) if x]) if home_bench else "N/A"
    away_bench_text = ", ".join([x for x in (_format_sofascore_player_inline(p) for p in away_bench) if x]) if away_bench else "N/A"
    home_missing_text = ", ".join([x for x in (_format_sofascore_player_inline(p) for p in home_missing) if x]) if home_missing else "N/A"
    away_missing_text = ", ".join([x for x in (_format_sofascore_player_inline(p) for p in away_missing) if x]) if away_missing else "N/A"

    tournament_name = ((event.get("tournament") or {}).get("name") if isinstance(event, dict) else None) or ""
    start_ts = event.get("startTimestamp") if isinstance(event, dict) else None
    match_date = None
    if start_ts:
        try:
            match_date = pd.to_datetime(int(start_ts), unit="s").strftime("%Y-%m-%d")
        except Exception:
            match_date = None

    lines = [
        SOFASCORE_CONTEXT_MARKER,
        "**Confirmed Lineups (Auto from SofaScore Widget):**",
        f"- SofaScore Event ID: {event_id}",
        f"- Lineups Confirmed: {'Yes' if bool((lineups_json or {}).get('confirmed')) else 'No'}",
    ]
    if tournament_name:
        lines.append(f"- Competition: {tournament_name}")
    if match_date:
        lines.append(f"- Date: {match_date}")

    lines.extend(
        [
            "",
            f"**{home_name} ({home_formation}):**",
            f"* **XI (payload position):** {home_xi_text}",
            "",
            f"**{away_name} ({away_formation}):**",
            f"* **XI (payload position):** {away_xi_text}",
            "",
            "Team News:",
            f"* {home_name} Bench: {home_bench_text}",
            f"* {away_name} Bench: {away_bench_text}",
            f"* {home_name} Missing: {home_missing_text}",
            f"* {away_name} Missing: {away_missing_text}",
        ]
    )
    return "\n".join(lines)


def _expand_sofascore_widget_context(context_text, home_team=None, away_team=None):
    raw = str(context_text or "")
    event_id = _extract_sofascore_event_id(raw)
    if not event_id:
        return raw
    if SOFASCORE_CONTEXT_MARKER in raw:
        return raw

    lineups_url = f"https://api.sofascore.com/api/v1/event/{event_id}/lineups"
    event_url = f"https://api.sofascore.com/api/v1/event/{event_id}"

    lineups_json, lineup_error = _sofascore_get_json(lineups_url)
    if lineups_json is None:
        print(f"[Warning] SofaScore lineups load failed for event {event_id}: {lineup_error}")
        return raw

    event_json, event_error = _sofascore_get_json(event_url)
    if event_json is None:
        print(f"[Warning] SofaScore event metadata load failed for event {event_id}: {event_error}")

    block = _build_sofascore_context_block(
        event_id=event_id,
        lineups_json=lineups_json,
        event_json=event_json,
        home_hint=home_team,
        away_hint=away_team,
    )
    print(f"[Info] SofaScore lineup context loaded from event id {event_id}.")
    return f"{raw.strip()}\n\n{block}\n" if raw.strip() else f"{block}\n"


def _load_live_context(path="match_context.txt", home_team=None, away_team=None):
    if not os.path.exists(path):
        return "No live context available (Lineups/Injuries missing)."
    try:
        with open(path, "r", encoding="utf-8") as f:
            context_text = f.read()
            return _expand_sofascore_widget_context(
                context_text=context_text,
                home_team=home_team,
                away_team=away_team,
            )
    except Exception:
        return "No live context available (Lineups/Injuries missing)."


def _parse_context_headers(context_text):
    headers = {"match": None, "date": None, "league": None}
    for raw_line in str(context_text).splitlines():
        line = re.sub(r"[*`#>\[\]]", "", raw_line).strip()
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


def get_opta_team_stats(team_name, league):
    """Load OPTA advanced stats from output_opta/{league}/{team}.xlsx.
    Aggregates player-level data into team-level summaries."""
    opta_dir = Path("output_opta") / league
    if not opta_dir.exists():
        return {}

    # --- Resolve file name (fuzzy match) ---
    target = _normalize_text(team_name)
    best_file = None
    for f in opta_dir.glob("*.xlsx"):
        if _normalize_text(f.stem) == target:
            best_file = f
            break
    if best_file is None:
        # Try partial / alias matching
        for alias in _team_aliases(team_name):
            alias_norm = _normalize_text(alias)
            for f in opta_dir.glob("*.xlsx"):
                if _normalize_text(f.stem) == alias_norm:
                    best_file = f
                    break
            if best_file:
                break
    if best_file is None:
        # Substring fallback
        for f in opta_dir.glob("*.xlsx"):
            if target in _normalize_text(f.stem) or _normalize_text(f.stem) in target:
                best_file = f
                break
    if best_file is None:
        return {}

    result = {"opta_file": best_file.name}
    try:
        xl = pd.ExcelFile(best_file)
        sheets = xl.sheet_names

        # --- Attacking ---
        if "Attacking" in sheets:
            df = pd.read_excel(best_file, sheet_name="Attacking")
            result["opta_goals"] = pd.to_numeric(df.get("goals"), errors="coerce").sum()
            result["opta_xg"] = pd.to_numeric(df.get("xg"), errors="coerce").sum()
            result["opta_shots"] = pd.to_numeric(df.get("shots"), errors="coerce").sum()
            result["opta_sot"] = pd.to_numeric(df.get("sot"), errors="coerce").sum()
            conv = pd.to_numeric(df.get("conv %"), errors="coerce").dropna()
            result["opta_conv_pct"] = float(conv.mean()) if len(conv) > 0 else None
            xgps = pd.to_numeric(df.get("xG per Shot"), errors="coerce").dropna()
            result["opta_xg_per_shot"] = float(xgps.mean()) if len(xgps) > 0 else None

        # --- Passing ---
        if "Passing" in sheets:
            df = pd.read_excel(best_file, sheet_name="Passing")
            op_total = pd.to_numeric(df.get("Open Play Passes_total"), errors="coerce").sum()
            op_succ = pd.to_numeric(df.get("Open Play Passes_successful"), errors="coerce").sum()
            result["opta_open_play_passes"] = float(op_total)
            result["opta_pass_pct"] = float(op_succ / op_total * 100) if op_total > 0 else None
            ft_total = pd.to_numeric(df.get("In Final Third_total"), errors="coerce").sum()
            ft_succ = pd.to_numeric(df.get("In Final Third_successful"), errors="coerce").sum()
            result["opta_final_third_passes"] = float(ft_total)
            result["opta_final_third_pct"] = float(ft_succ / ft_total * 100) if ft_total > 0 else None
            result["opta_crosses"] = pd.to_numeric(df.get("Crosses_total"), errors="coerce").sum()
            result["opta_through_balls"] = pd.to_numeric(df.get("through balls"), errors="coerce").sum()

        # --- Defending ---
        if "Defending" in sheets:
            df = pd.read_excel(best_file, sheet_name="Defending")
            result["opta_tackles"] = pd.to_numeric(df.get("tackles"), errors="coerce").sum()
            result["opta_interceptions"] = pd.to_numeric(df.get("ints"), errors="coerce").sum()
            result["opta_blocks"] = pd.to_numeric(df.get("blocks"), errors="coerce").sum()
            result["opta_clearances"] = pd.to_numeric(df.get("clearances"), errors="coerce").sum()
            gd_won = pd.to_numeric(df.get("Ground Duels_won"), errors="coerce").sum()
            gd_total = pd.to_numeric(df.get("Ground Duels_total"), errors="coerce").sum()
            result["opta_ground_duels_pct"] = float(gd_won / gd_total * 100) if gd_total > 0 else None
            ad_won = pd.to_numeric(df.get("Aerial Duels_won"), errors="coerce").sum()
            ad_total = pd.to_numeric(df.get("Aerial Duels_total"), errors="coerce").sum()
            result["opta_aerial_duels_pct"] = float(ad_won / ad_total * 100) if ad_total > 0 else None

        # --- Carrying ---
        if "Carrying" in sheets:
            df = pd.read_excel(best_file, sheet_name="Carrying")
            result["opta_progressive_carries"] = pd.to_numeric(df.get("Progressive_total"), errors="coerce").sum()
            prog_dist = pd.to_numeric(df.get("Progressive_distance (m)"), errors="coerce").sum()
            result["opta_progressive_distance"] = float(prog_dist)
            result["opta_carries_to_shot"] = pd.to_numeric(df.get("Ended With_shot"), errors="coerce").sum()
            result["opta_carries_to_goal"] = pd.to_numeric(df.get("Ended With_goal"), errors="coerce").sum()
            result["opta_carries_to_chance"] = pd.to_numeric(df.get("Ended With_chance"), errors="coerce").sum()

        # --- Goalkeeping ---
        if "Goalkeeping" in sheets:
            df = pd.read_excel(best_file, sheet_name="Goalkeeping")
            save_pct = pd.to_numeric(df.get("save %"), errors="coerce").dropna()
            result["opta_save_pct"] = float(save_pct.mean()) if len(save_pct) > 0 else None
            result["opta_goals_conceded"] = pd.to_numeric(df.get("goals conceded"), errors="coerce").sum()
            result["opta_saves"] = pd.to_numeric(df.get("saves made"), errors="coerce").sum()
            gp = pd.to_numeric(df.get("goals prevented"), errors="coerce").dropna()
            result["opta_goals_prevented"] = float(gp.sum()) if len(gp) > 0 else None

    except Exception as e:
        result["opta_error"] = str(e)

    return result


def _format_opta_section(label, opta):
    """Format OPTA stats dict into a readable prompt section."""
    if not opta or "opta_file" not in opta:
        return f"- {label}: No OPTA data available"
    lines = [f"- {label} (source: {opta.get('opta_file', 'N/A')}):"]
    lines.append(f"  Attacking: xG={_fmt_num(opta.get('opta_xg'))}, Goals={_fmt_num(opta.get('opta_goals'))}, Shots={_fmt_num(opta.get('opta_shots'))}, SoT={_fmt_num(opta.get('opta_sot'))}, Conv%={_fmt_num(opta.get('opta_conv_pct'))}, xG/Shot={_fmt_num(opta.get('opta_xg_per_shot'))}")
    lines.append(f"  Passing: OpenPlay%={_fmt_num(opta.get('opta_pass_pct'))}, FinalThird%={_fmt_num(opta.get('opta_final_third_pct'))}, Crosses={_fmt_num(opta.get('opta_crosses'))}, ThroughBalls={_fmt_num(opta.get('opta_through_balls'))}")
    lines.append(f"  Defending: Tackles={_fmt_num(opta.get('opta_tackles'))}, Ints={_fmt_num(opta.get('opta_interceptions'))}, Blocks={_fmt_num(opta.get('opta_blocks'))}, GroundDuels%={_fmt_num(opta.get('opta_ground_duels_pct'))}, AerialDuels%={_fmt_num(opta.get('opta_aerial_duels_pct'))}")
    lines.append(f"  Carrying: ProgCarries={_fmt_num(opta.get('opta_progressive_carries'))}, ProgDist={_fmt_num(opta.get('opta_progressive_distance'))}m, Carry->Shot={_fmt_num(opta.get('opta_carries_to_shot'))}, Carry->Goal={_fmt_num(opta.get('opta_carries_to_goal'))}")
    lines.append(f"  GK: Save%={_fmt_num(opta.get('opta_save_pct'))}, Saves={_fmt_num(opta.get('opta_saves'))}, GoalsPrevented={_fmt_num(opta.get('opta_goals_prevented'))}")
    return "\n".join(lines)


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
    tactical_scenarios,
    home_opta=None,
    away_opta=None,
):
    home_opta = home_opta if isinstance(home_opta, dict) else {}
    away_opta = away_opta if isinstance(away_opta, dict) else {}
    home_ppda = _pick_first(home_flow, ["calc_PPDA", "PPDA"])
    away_ppda = _pick_first(away_flow, ["calc_PPDA", "PPDA"])
    home_poss = _pick_first(home_squad, ["Poss", "averageBallPossession", "Possession"])
    away_poss = _pick_first(away_squad, ["Poss", "averageBallPossession", "Possession"])
    home_g90 = _pick_first(home_squad, ["Per 90 Minutes_Gls", "goalsScored_per_90", "Goals/90"])
    away_g90 = _pick_first(away_squad, ["Per 90 Minutes_Gls", "goalsScored_per_90", "Goals/90"])
    home_ga90 = _pick_first(home_squad, ["Per 90 Minutes_GA", "goalsConceded_per_90", "GA/90"])
    away_ga90 = _pick_first(away_squad, ["Per 90 Minutes_GA", "goalsConceded_per_90", "GA/90"])
    home_xg90 = _pick_first(home_squad, ["Per 90 Minutes_xG", "xG/90", "Expected_xG", "xG"])
    away_xg90 = _pick_first(away_squad, ["Per 90 Minutes_xG", "xG/90", "Expected_xG", "xG"])
    home_xa90 = _pick_first(home_squad, ["Per 90 Minutes_xAG", "xA/90", "Expected_xAG", "xA"])
    away_xa90 = _pick_first(away_squad, ["Per 90 Minutes_xAG", "xA/90", "Expected_xAG", "xA"])
    lineup_ctx = sim.get("lineup_context") if isinstance(sim, dict) else {}
    lineup_ctx = lineup_ctx if isinstance(lineup_ctx, dict) else {}
    home_lineup_metrics = lineup_ctx.get("home_lineup_metrics") if isinstance(lineup_ctx, dict) else {}
    away_lineup_metrics = lineup_ctx.get("away_lineup_metrics") if isinstance(lineup_ctx, dict) else {}
    home_lineup_metrics = home_lineup_metrics if isinstance(home_lineup_metrics, dict) else {}
    away_lineup_metrics = away_lineup_metrics if isinstance(away_lineup_metrics, dict) else {}
    progression_ctx = sim.get("progression_context") if isinstance(sim, dict) else {}
    progression_ctx = progression_ctx if isinstance(progression_ctx, dict) else {}
    math_ctx = sim.get("math_winner_context") if isinstance(sim, dict) else {}
    math_ctx = math_ctx if isinstance(math_ctx, dict) else {}

    if home_xg90 is None:
        home_xg90 = _pick_first(((sim.get("xg_input") or {}).get("home") or {}).get("attack", {}), ["xg_per_game"])
    if away_xg90 is None:
        away_xg90 = _pick_first(((sim.get("xg_input") or {}).get("away") or {}).get("attack", {}), ["xg_per_game"])
    if home_xa90 is None:
        home_xa90 = home_lineup_metrics.get("xa_p90")
    if away_xa90 is None:
        away_xa90 = away_lineup_metrics.get("xa_p90")

    home_xt = _pick_first(home_flow, ["xT", "xt", "xT_per_90", "xt_proxy"])
    away_xt = _pick_first(away_flow, ["xT", "xt", "xT_per_90", "xt_proxy"])
    if home_xt is None:
        home_xt = progression_ctx.get("home_xt_proxy", home_lineup_metrics.get("xt_proxy"))
    if away_xt is None:
        away_xt = progression_ctx.get("away_xt_proxy", away_lineup_metrics.get("xt_proxy"))

    key_matchups = sim.get("key_matchups", []) if isinstance(sim, dict) else []
    key_matchups = key_matchups if isinstance(key_matchups, list) else []
    key_matchups_text = "\n".join([f"- {m}" for m in key_matchups[:6]]) if key_matchups else "- N/A"

    position_battles = sim.get("position_battles", []) if isinstance(sim, dict) else []
    position_battles = position_battles if isinstance(position_battles, list) else []
    if position_battles:
        battle_rows = []
        for battle in position_battles[:8]:
            if not isinstance(battle, dict):
                continue
            perspective = "Home" if battle.get("perspective") == "home" else "Away"
            edge = str(battle.get("edge", "even")).lower()
            if edge == "home":
                edge_label = home
            elif edge == "away":
                edge_label = away
            else:
                edge_label = "สูสี"
            battle_rows.append(
                "- "
                + f"{perspective} {battle.get('zone', 'N/A')}: "
                + f"{battle.get('attacker', 'N/A')} vs {battle.get('defender', 'N/A')} "
                + f"| duel={_fmt_num(battle.get('duel_score'))} "
                + f"| edge={edge_label} "
                + f"| xG/90={_fmt_num(battle.get('xg_p90'))} "
                + f"| xA/90={_fmt_num(battle.get('xa_p90'))} "
                + f"| xT={_fmt_num(battle.get('xt_proxy'))}"
            )
        position_battles_text = "\n".join(battle_rows) if battle_rows else "- N/A"
    else:
        position_battles_text = "- N/A"

    math_winner_side = str(math_ctx.get("winner_side", "none")).lower()
    if math_winner_side == "home":
        math_winner_text = f"{home} ได้เปรียบ"
    elif math_winner_side == "away":
        math_winner_text = f"{away} ได้เปรียบ"
    else:
        math_winner_text = "ไม่มีฝั่งได้เปรียบชัดเจน"

    qc_text = " | ".join(qc_flags) if qc_flags else "No critical QC flags"
    home_rated_text = ", ".join(home_top_rated) if home_top_rated else "N/A"
    away_rated_text = ", ".join(away_top_rated) if away_top_rated else "N/A"
    home_scorer_text = ", ".join(home_top_scorers) if home_top_scorers else "N/A"
    away_scorer_text = ", ".join(away_top_scorers) if away_top_scorers else "N/A"

    tactical_text_lines = []
    if tactical_scenarios:
        for scen in tactical_scenarios:
            name = scen.get("scenario", "Unknown")
            prob = scen.get("probability_pct", 0.0)
            goal_prob = scen.get("goal_probability_pct", 0.0)
            conf = scen.get("confidence", "low")
            tactical_text_lines.append(f"- {name} (โอกาสเกิด: {prob}%, โอกาสเป็นประตู: {goal_prob}%, ความเชื่อมั่น: {conf})")
    tactical_text = "\n".join(tactical_text_lines) if tactical_text_lines else "No specific tactical scenarios generated."

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
- Math Winner Signal: {math_winner_text} (home_ratio={_fmt_num(math_ctx.get('home_ratio'))}, away_ratio={_fmt_num(math_ctx.get('away_ratio'))})
- Math Winner Bonus: {home} {_fmt_pct(_safe_float(math_ctx.get('home_bonus'), 0.0) * 100.0)} | {away} {_fmt_pct(_safe_float(math_ctx.get('away_bonus'), 0.0) * 100.0)}
- Lineup Source: {home}={lineup_ctx.get('home_source', 'N/A')} ({lineup_ctx.get('home_matched', 0)}/11) | {away}={lineup_ctx.get('away_source', 'N/A')} ({lineup_ctx.get('away_matched', 0)}/11)
- Lineup Confidence: {_fmt_pct(_safe_float(lineup_ctx.get('confidence'), 0.0) * 100.0)}
- Lineup Metrics {home}: xG/90={_fmt_num(home_lineup_metrics.get('xg_p90'))}, xA/90={_fmt_num(home_lineup_metrics.get('xa_p90'))}, xT={_fmt_num(home_lineup_metrics.get('xt_proxy'))}, Attack={_fmt_num(home_lineup_metrics.get('attack'))}, Defense={_fmt_num(home_lineup_metrics.get('defense'))}
- Lineup Metrics {away}: xG/90={_fmt_num(away_lineup_metrics.get('xg_p90'))}, xA/90={_fmt_num(away_lineup_metrics.get('xa_p90'))}, xT={_fmt_num(away_lineup_metrics.get('xt_proxy'))}, Attack={_fmt_num(away_lineup_metrics.get('attack'))}, Defense={_fmt_num(away_lineup_metrics.get('defense'))}

Team Style Snapshot
- {home}: PPDA={_fmt_num(home_ppda)}, Possession={_fmt_pct(home_poss)}, Goals/90={_fmt_num(home_g90)}, Conceded/90={_fmt_num(home_ga90)}, xG/90={_fmt_num(home_xg90)}, xA/90={_fmt_num(home_xa90)}, xT={_fmt_num(home_xt)}
- {away}: PPDA={_fmt_num(away_ppda)}, Possession={_fmt_pct(away_poss)}, Goals/90={_fmt_num(away_g90)}, Conceded/90={_fmt_num(away_ga90)}, xG/90={_fmt_num(away_xg90)}, xA/90={_fmt_num(away_xa90)}, xT={_fmt_num(away_xt)}
- Key Rated ({home}): {home_rated_text}
- Key Rated ({away}): {away_rated_text}
- Top Scorers ({home}): {home_scorer_text}
- Top Scorers ({away}): {away_scorer_text}

OPTA Advanced Stats (theanalyst.com)
{_format_opta_section(home, home_opta)}
{_format_opta_section(away, away_opta)}

Model Key Matchups
{key_matchups_text}

Tactical Simulation Scenarios (AI Model Generated)
{tactical_text}

Position Battles (Player vs Player)
{position_battles_text}

Live Context / Team News
{context_text}

ข้อกำหนดรูปแบบ (ต้องทำตาม)
1) เปิดรายงานด้วยย่อหน้าเกริ่น 1 ย่อหน้า แล้วคั่นด้วย ---
2) ลำดับการวิเคราะห์ต้องเป็น:
   - เริ่มจากอ่าน Confirmed Lineups และบอกคุณภาพข้อมูล lineup
   - ดึงข้อมูลผู้เล่นจากรายชื่อ แล้วเปรียบเทียบรายตำแหน่งจาก Position Battles
   - วิเคราะห์แผนการเล่น + สถานะทีม โดยใช้ PPDA/xG/xA/xT เป็นหลัก
   - สรุปผลจากการจำลอง (Top 3 Scores + Math Winner Signal) ก่อนฟันธง
3) ต้องมีหัวข้อหลัก 2 ส่วนดังนี้:
# **ส่วนที่ 1: การวิเคราะห์ภาพรวมทีม (Team Overview Analysis)**
และ
# **ส่วนที่ 2: การวิเคราะห์ผู้เล่นรายบุคคล (Player Analysis)**
4) ส่วนที่ 1 ต้องมีหัวข้อย่อย:
- สภาพทีม & ข่าวล่าสุด
- การวิเคราะห์เชิงกลยุทธ์ & แทคติก (ต้องพูดถึง Tactical Scenarios ที่ให้ไป)
- ตารางเปรียบเทียบกลยุทธ์ (ต้องเป็นตาราง Markdown)
- ภาพรวมและแนวโน้ม
- บทสรุปภาพรวม (ต้องฟันธงสกอร์และความมั่นใจ สูง/กลาง/ต่ำ พร้อมอ้าง Top 3 Scores และ Math Winner Signal)
5) ส่วนที่ 2 ต้องมีหัวข้อย่อย:
- เจาะลึกผู้เล่นหลัก
- ดวลกันตัวต่อตัว
- ตัวทีเด็ด (X-Factor)
6) ใช้โทนมืออาชีพ ชัดเจน มีเหตุผล ไม่เวอร์เกินข้อมูล
7) ห้ามแต่งสถิติที่ไม่มีในอินพุต ถ้าข้อมูลไม่พอให้เขียนว่า "ข้อมูลไม่พอ"
8) ปิดท้ายด้วยบรรทัด "รายงานโดย: AI Analyst Systems"
"""


def _resolve_gemini_models(model=None):
    if model:
        return [str(model).strip()]

    env_models = os.getenv("GEMINI_MODELS", "").strip()
    if env_models:
        models = [m.strip() for m in env_models.split(",") if m.strip()]
        if models:
            return models

    env_model = os.getenv("GEMINI_MODEL", "").strip()
    if env_model:
        return [env_model]

    # Keep a stable default first for free-tier compatibility, then fallback.
    return ["gemini-flash-latest", "gemini-2.0-flash"]


def _generate_ai_report(prompt, api_key, model=None, max_retries=3, timeout_sec=90):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "topP": 0.95},
    }

    model_candidates = _resolve_gemini_models(model)
    last_error = None

    for current_model in model_candidates:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    api_url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=timeout_sec,
                )
            except Exception as ex:
                last_error = f"request_failed[{current_model}]: {ex}"
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                break

            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception:
                    return None, f"invalid_json_from_gemini[{current_model}]"
                text = _extract_gemini_text(data)
                if text:
                    return text, None
                return None, f"gemini_returned_no_text[{current_model}]"

            body = response.text.strip().replace("\n", " ")
            if len(body) > 240:
                body = body[:240] + "..."
            last_error = f"gemini_http_{response.status_code}[{current_model}]: {body}"

            if response.status_code in {429, 500, 502, 503, 504}:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                # Try next model candidate after final retry.
                break

            return None, last_error

    return None, last_error or "unknown_gemini_error"


def _try_simulator(
    home,
    away,
    league,
    home_sim_stats,
    away_sim_stats,
    home_prog,
    away_prog,
    context_text,
    home_flow=None,
    away_flow=None,
):
    home_xg_data = None
    away_xg_data = None
    try:
        import xg_engine
        import simulator_v9

        eng = xg_engine.XGEngine(league)
        home_xg_data = eng.get_team_rolling_stats(home, n_games=10)
        away_xg_data = eng.get_team_rolling_stats(away, n_games=10)
        if not (home_xg_data and away_xg_data):
            raise RuntimeError("xG data missing")
        sim = simulator_v9.simulate_match(
            home_xg_data,
            away_xg_data,
            home_sim_stats,
            away_sim_stats,
            iterations=10000,
            league=league,
            home_team=home,
            away_team=away,
            context_text=context_text,
            home_progression=home_prog,
            away_progression=away_prog,
            home_flow=home_flow,
            away_flow=away_flow,
        )
        sim["xg_input"] = {"home": home_xg_data, "away": away_xg_data}
        sim.setdefault("lineup_context", {})
        sim.setdefault("fatigue_context", {})
        sim.setdefault("progression_context", {})
        sim.setdefault("key_matchups", [])
        sim.setdefault("position_battles", [])
        sim.setdefault("math_winner_context", {})
        return sim
    except Exception as ex:
        print(f"[Warning] simulator_v9 unavailable, fallback Poisson: {ex}")
        l_home = float((home_sim_stats or {}).get("goals_scored_per_game", 1.45))
        l_away = float((away_sim_stats or {}).get("goals_scored_per_game", 1.25))
        sim = _poisson_summary(l_home, l_away)
        sim["xg_input"] = {"home": home_xg_data or {}, "away": away_xg_data or {}}
        sim["lineup_context"] = {}
        sim["fatigue_context"] = {}
        sim["progression_context"] = {}
        sim["key_matchups"] = []
        sim["position_battles"] = []
        sim["math_winner_context"] = {}
        return sim


def _normalize_league_for_demo_v2(league_name):
    raw = str(league_name or "").strip()
    if not raw:
        return "All"
    normalized = _normalize_text(raw).replace(" ", "_")
    mapping = {
        "premier_league": "Premier_League",
        "la_liga": "La_Liga",
        "serie_a": "Serie_A",
        "bundesliga": "Bundesliga",
        "ligue_1": "Ligue_1",
    }
    return mapping.get(normalized, "All")


def _run_demo_v2_shadow(home_team, away_team, league):
    league_key = _normalize_league_for_demo_v2(league)
    try:
        import numpy as np

        from demo_model_v2.data_loader import DataLoader
        from demo_model_v2.feature_engine import FeatureEngine
        from demo_model_v2.match_log_loader import MatchLogLoader
        from demo_model_v2.player_impact_engine import PlayerImpactEngine
        from demo_model_v2.poisson_model import PoissonModel
        from demo_model_v2.simulator import MatchSimulator
    except Exception as ex:
        return {
            "enabled": False,
            "status": "unavailable",
            "reason": f"import_error: {ex}",
            "league_used": league_key,
        }

    try:
        loader = DataLoader("sofascore_team_data")
        df_raw = loader.load_data(league_key)
        engine = FeatureEngine()
        df_processed = engine.calculate_feature_metrics(df_raw)

        log_loader = MatchLogLoader("Match Logs")
        impact_engine = PlayerImpactEngine("sofaplayer")
        home_tax = impact_engine.calculate_missing_tax(home_team, league_key, None)
        away_tax = impact_engine.calculate_missing_tax(away_team, league_key, None)

        home_ratings = engine.get_team_ratings(
            df_processed,
            home_team,
            match_log_loader=log_loader,
            venue="Home",
            player_tax=home_tax,
        )
        away_ratings = engine.get_team_ratings(
            df_processed,
            away_team,
            match_log_loader=log_loader,
            venue="Away",
            player_tax=away_tax,
        )

        model = PoissonModel()
        lambda_home, lambda_away = model.predict_match_lambdas(
            home_ratings,
            away_ratings,
            league_avg_home_goals=1.6,
            league_avg_away_goals=1.2,
        )
        matrix = model.get_score_probability_matrix(lambda_home, lambda_away)
        score_idx = np.unravel_index(np.argmax(matrix), matrix.shape)
        most_likely_score = f"{int(score_idx[0])}-{int(score_idx[1])}"

        p_home = float(np.tril(matrix, -1).sum() * 100.0)
        p_draw = float(np.trace(matrix) * 100.0)
        p_away = float(np.triu(matrix, 1).sum() * 100.0)

        mc = MatchSimulator().run_monte_carlo(lambda_home, lambda_away, n_sims=10000)

        return {
            "enabled": True,
            "status": "ok",
            "model": "demo_model_v2",
            "league_used": league_key,
            "home_win_prob": round(p_home, 2),
            "draw_prob": round(p_draw, 2),
            "away_win_prob": round(p_away, 2),
            "home_win_prob_mc": round(float(mc.get("home_win", 0.0) * 100.0), 2),
            "draw_prob_mc": round(float(mc.get("draw", 0.0) * 100.0), 2),
            "away_win_prob_mc": round(float(mc.get("away_win", 0.0) * 100.0), 2),
            "expected_goals_home": round(float(lambda_home), 3),
            "expected_goals_away": round(float(lambda_away), 3),
            "most_likely_score": most_likely_score,
            "home_rating_source": home_ratings.get("source"),
            "away_rating_source": away_ratings.get("source"),
        }
    except Exception as ex:
        return {
            "enabled": False,
            "status": "failed",
            "reason": str(ex),
            "league_used": league_key,
        }


def _build_demo_v2_appendix(home, away, demo_v2, sim_v9=None):
    section_title = "## ภาคผนวก: Demo Model v2 (Shadow)"
    if not isinstance(demo_v2, dict):
        return f"{section_title}\n\n- สถานะ: ไม่ได้รัน (ไม่มีข้อมูล demo_v2)"

    if not demo_v2.get("enabled"):
        reason = demo_v2.get("reason") or demo_v2.get("status") or "unknown"
        league_used = demo_v2.get("league_used", "N/A")
        return (
            f"{section_title}\n\n"
            f"- สถานะ: ไม่พร้อมใช้งาน\n"
            f"- ลีกที่พยายามใช้: `{league_used}`\n"
            f"- เหตุผล: `{reason}`"
        )

    delta_lines = []
    if isinstance(sim_v9, dict):
        try:
            delta_lines = [
                f"- Delta vs v9 (Home): {float(demo_v2.get('home_win_prob', 0.0)) - float(sim_v9.get('home_win_prob', 0.0)):+.2f}%",
                f"- Delta vs v9 (Draw): {float(demo_v2.get('draw_prob', 0.0)) - float(sim_v9.get('draw_prob', 0.0)):+.2f}%",
                f"- Delta vs v9 (Away): {float(demo_v2.get('away_win_prob', 0.0)) - float(sim_v9.get('away_win_prob', 0.0)):+.2f}%",
                f"- Delta xG Home: {float(demo_v2.get('expected_goals_home', 0.0)) - float(sim_v9.get('expected_goals_home', 0.0)):+.3f}",
                f"- Delta xG Away: {float(demo_v2.get('expected_goals_away', 0.0)) - float(sim_v9.get('expected_goals_away', 0.0)):+.3f}",
            ]
        except Exception:
            delta_lines = []

    lines = [
        section_title,
        "",
        "- สถานะ: รันสำเร็จ",
        f"- ลีกที่ใช้: `{demo_v2.get('league_used', 'N/A')}`",
        f"- โมเดล: `{demo_v2.get('model', 'demo_model_v2')}`",
        f"- ความน่าจะเป็น 1X2 (Poisson Matrix): {home} {demo_v2.get('home_win_prob')}% | Draw {demo_v2.get('draw_prob')}% | {away} {demo_v2.get('away_win_prob')}%",
        f"- ความน่าจะเป็น 1X2 (Monte Carlo): {home} {demo_v2.get('home_win_prob_mc')}% | Draw {demo_v2.get('draw_prob_mc')}% | {away} {demo_v2.get('away_win_prob_mc')}%",
        f"- xG: {home} {demo_v2.get('expected_goals_home')} | {away} {demo_v2.get('expected_goals_away')}",
        f"- สกอร์ที่น่าจะเป็นที่สุด: {demo_v2.get('most_likely_score', 'N/A')}",
        f"- Source Ratings: Home={demo_v2.get('home_rating_source', 'N/A')} | Away={demo_v2.get('away_rating_source', 'N/A')}",
    ]
    if delta_lines:
        lines.append("- Comparison to v9:")
        lines.extend(delta_lines)
    return "\n".join(lines)


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
    stats_league = home_league or away_league or "Premier_League"

    if home_league and away_league and home_league != away_league:
        print(f"[Warning] League mismatch: home={home_league}, away={away_league}. Using {stats_league} for model data.")

    home_sim_stats = get_simulation_stats(home, stats_league)
    away_sim_stats = get_simulation_stats(away, stats_league)
    home_prog = get_progression_stats(home, stats_league)
    away_prog = get_progression_stats(away, stats_league)

    context_text = _load_live_context("match_context.txt", home_team=home, away_team=away)
    context_headers = _parse_context_headers(context_text)
    context_league = str(context_headers.get("league") or "").strip()
    league = context_league or stats_league
    if context_league and context_league != stats_league:
        print(f"[Info] Context league '{context_league}' overrides output league (model data still uses '{stats_league}').")

    qc_flags, context_header = run_data_qc(home, away, league, context_text, home_league, away_league)

    home_flow = get_game_flow_stats(home, league)
    away_flow = get_game_flow_stats(away, league)
    sim = _try_simulator(
        home,
        away,
        stats_league,
        home_sim_stats,
        away_sim_stats,
        home_prog,
        away_prog,
        context_text,
        home_flow=home_flow,
        away_flow=away_flow,
    )
    demo_v2_shadow = _run_demo_v2_shadow(home, away, stats_league)

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

    home_squad = get_squad_stats(home, league)
    away_squad = get_squad_stats(away, league)
    home_opta = get_opta_team_stats(home, league)
    away_opta = get_opta_team_stats(away, league)
    if home_opta:
        print(f"[Info] OPTA data loaded for {home}: {home_opta.get('opta_file', 'N/A')}")
    if away_opta:
        print(f"[Info] OPTA data loaded for {away}: {away_opta.get('opta_file', 'N/A')}")
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

    home_ppda = _pick_first(home_flow, ["calc_PPDA", "PPDA"])
    away_ppda = _pick_first(away_flow, ["calc_PPDA", "PPDA"])
    home_poss = _pick_first(home_squad, ["Poss", "averageBallPossession", "Possession"])
    away_poss = _pick_first(away_squad, ["Poss", "averageBallPossession", "Possession"])
    home_g90 = _pick_first(home_squad, ["Per 90 Minutes_Gls", "goalsScored_per_90", "Goals/90"])
    away_g90 = _pick_first(away_squad, ["Per 90 Minutes_Gls", "goalsScored_per_90", "Goals/90"])
    home_ga90 = _pick_first(home_squad, ["Per 90 Minutes_GA", "goalsConceded_per_90", "GA/90"])
    away_ga90 = _pick_first(away_squad, ["Per 90 Minutes_GA", "goalsConceded_per_90", "GA/90"])
    home_xg90 = _pick_first(home_squad, ["Per 90 Minutes_xG", "xG/90", "Expected_xG", "xG"])
    away_xg90 = _pick_first(away_squad, ["Per 90 Minutes_xG", "xG/90", "Expected_xG", "xG"])
    home_xa90 = _pick_first(home_squad, ["Per 90 Minutes_xAG", "xA/90", "Expected_xAG", "xA"])
    away_xa90 = _pick_first(away_squad, ["Per 90 Minutes_xAG", "xA/90", "Expected_xAG", "xA"])
    home_xt = _pick_first(home_flow, ["xT", "xt", "xT_per_90", "xt_proxy"], home_prog.get("xt_proxy"))
    away_xt = _pick_first(away_flow, ["xT", "xt", "xT_per_90", "xt_proxy"], away_prog.get("xt_proxy"))

    # Fallbacks for sparse stats sheets to reduce nulls in Team_Style_Snapshot.
    if home_g90 is None:
        home_g90 = _pick_first(home_sim_stats, ["goals_scored_per_game"])
    if away_g90 is None:
        away_g90 = _pick_first(away_sim_stats, ["goals_scored_per_game"])
    if home_ga90 is None:
        home_ga90 = _pick_first(home_sim_stats, ["goals_conceded_per_game"])
    if away_ga90 is None:
        away_ga90 = _pick_first(away_sim_stats, ["goals_conceded_per_game"])
    if home_poss is None:
        home_poss = _pick_first(home_squad, ["averageBallPossession"])
    if away_poss is None:
        away_poss = _pick_first(away_squad, ["averageBallPossession"])

    xg_input = sim.get("xg_input", {})
    if home_xg90 is None:
        home_xg90 = _pick_first((xg_input.get("home") or {}).get("attack") or {}, ["xg_per_game"])
    if away_xg90 is None:
        away_xg90 = _pick_first((xg_input.get("away") or {}).get("attack") or {}, ["xg_per_game"])

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
            tactical_scenarios=tactical_scenarios.get("scenarios", []),
            home_opta=home_opta,
            away_opta=away_opta,
        )
        ai_report, analysis_error = _generate_ai_report(prompt=prompt, api_key=gemini_key)
        if ai_report:
            demo_appendix = _build_demo_v2_appendix(home, away, demo_v2_shadow, sim_v9=sim)
            if demo_appendix:
                ai_report = ai_report.rstrip() + "\n\n---\n\n" + demo_appendix + "\n"
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
        "Flow_Data": {"home": home_flow, "away": away_flow},
        "Tactical_Scenarios": tactical_scenarios,
        "Calibration_Context": sim.get("calibration_context", {}),
        "Simulator_Tactical_Context": sim.get("tactical_context", {}),
        "Demo_v2_Shadow": demo_v2_shadow,
        "Team_Style_Snapshot": {
            "home": {
                "ppda": _safe_float(home_ppda, None),
                "possession_pct": _safe_float(home_poss, None),
                "goals_per_90": _safe_float(home_g90, None),
                "conceded_per_90": _safe_float(home_ga90, None),
                "xg_per_90": _safe_float(home_xg90, None),
                "xa_per_90": _safe_float(home_xa90, None),
                "xt_proxy": _safe_float(home_xt, None),
            },
            "away": {
                "ppda": _safe_float(away_ppda, None),
                "possession_pct": _safe_float(away_poss, None),
                "goals_per_90": _safe_float(away_g90, None),
                "conceded_per_90": _safe_float(away_ga90, None),
                "xg_per_90": _safe_float(away_xg90, None),
                "xa_per_90": _safe_float(away_xa90, None),
                "xt_proxy": _safe_float(away_xt, None),
            },
        },
        "Lineup_Context": sim.get("lineup_context", {}),
        "Fatigue_Context": sim.get("fatigue_context", {}),
        "Progression_Context": sim.get("progression_context", {}),
        "Key_Matchups": sim.get("key_matchups", []),
        "Position_Battles": sim.get("position_battles", []),
        "Math_Winner_Context": sim.get("math_winner_context", {}),
        "XG_Input": sim.get("xg_input", {}),
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
