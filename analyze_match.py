
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
        return {
            "goals_scored_per_game": float(row.get("goalsScored_per_90", 0.0)),
            "goals_conceded_per_game": float(row.get("goalsConceded_per_90", 0.0)),
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
        matches = max(1.0, float(row.get("Matches_Played", 1)))
        opp_half_passes_p90 = float(row.get("accurateOppositionHalfPasses", 0.0)) / matches
        dribbles_p90 = float(row.get("successfulDribbles_per_90", row.get("successfulDribbles", 0.0) / matches))
        big_created_p90 = float(row.get("bigChancesCreated", 0.0)) / matches
        inside_box_shots_p90 = float(row.get("shotsFromInsideTheBox", 0.0)) / matches
        fast_breaks_p90 = float(row.get("fastBreaks", 0.0)) / matches

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


def main():
    if len(sys.argv) < 3:
        print("Usage: python analyze_match.py <HomeTeam> <AwayTeam>")
        return

    home = sys.argv[1].strip()
    away = sys.argv[2].strip()
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

    home_flow = get_game_flow_stats(home, league)
    away_flow = get_game_flow_stats(away, league)
    home_squad = get_squad_stats(home, league)
    away_squad = get_squad_stats(away, league)
    home_top_rated, home_top_scorers = get_top_players(home, league, top_n=3)
    away_top_rated, away_top_scorers = get_top_players(away, league, top_n=3)

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
        "Model_Version": sim.get("model_version", "unknown"),
        "QC_Flags": qc_flags,
        "Context_Header": context_header,
        "Bet_Data": bet_data,
        "Bet_Detail": bet_detail,
        "Progression_Data": {"home": home_prog, "away": away_prog},
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
