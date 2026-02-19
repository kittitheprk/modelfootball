
import json
import math
import os
import re
import shutil
import unicodedata
from datetime import datetime

import pandas as pd

NO_BET_LABEL = "No Bet"
TEAM_SUFFIX_TOKENS = {"fc", "cf", "sc", "afc", "ac"}
CALIBRATION_FILE = "model_calibration.json"
PERFORMANCE_FILE = "model_performance.json"
QUALITY_GATES = {
    "min_completed_matches": 30,
    "result_accuracy_min": 0.50,
    "brier_1x2_max": 0.62,
    "log_loss_1x2_max": 1.05,
    "score_mae_max": 1.35,
    "xg_mae_max": 0.95,
}


def backup_tracker(excel_file, max_backups=10):
    if not os.path.exists(excel_file):
        return
    backup_dir = os.path.join(os.path.dirname(excel_file) or ".", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"prediction_tracker_backup_{ts}.xlsx"
    backup_path = os.path.join(backup_dir, backup_name)
    try:
        shutil.copy2(excel_file, backup_path)
        backups = sorted(
            [f for f in os.listdir(backup_dir) if f.startswith("prediction_tracker_backup_") and f.endswith(".xlsx")]
        )
        while len(backups) > max_backups:
            old = backups.pop(0)
            os.remove(os.path.join(backup_dir, old))
    except Exception as e:
        print(f"[Backup Warning] {e}")


def _normalize_text_key(value):
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^0-9a-zA-Z\s]", " ", text).lower()
    return re.sub(r"\s+", " ", text).strip()


def _normalize_team_key(name):
    norm = _normalize_text_key(name)
    if not norm:
        return ""
    tokens = [t for t in norm.split() if t not in TEAM_SUFFIX_TOKENS]
    return " ".join(tokens) if tokens else norm


def _normalize_date_key(value):
    parsed = pd.to_datetime(pd.Series([value]), errors="coerce")
    if parsed.notna().iloc[0]:
        return parsed.dt.strftime("%Y-%m-%d").iloc[0]
    return str(value).strip()[:10]


def _first_nonblank(row, candidates):
    if row is None:
        return None
    for col in candidates:
        if col in row.index:
            val = row.get(col)
            if not _is_blank_value(val):
                return val
    return None


def _duplicate_mask(df, row_date, row_match, row_home=None, row_away=None):
    if df is None or df.empty:
        return pd.Series([], dtype=bool)

    date_key = _normalize_date_key(row_date)
    date_col = df.get("Date", pd.Series([""] * len(df)))
    date_norm = pd.to_datetime(date_col, errors="coerce")
    date_norm = date_norm.dt.strftime("%Y-%m-%d").where(date_norm.notna(), date_col.astype(str).str.slice(0, 10))
    date_mask = date_norm == date_key

    match_col = df.get("Match", pd.Series([""] * len(df)))
    match_mask = match_col.astype(str).apply(_normalize_text_key) == _normalize_text_key(row_match)
    mask = date_mask & match_mask
    if mask.any():
        return mask

    home_col = None
    away_col = None
    if "Home_Team" in df.columns:
        home_col = "Home_Team"
    elif "Home" in df.columns:
        home_col = "Home"
    if "Away_Team" in df.columns:
        away_col = "Away_Team"
    elif "Away" in df.columns:
        away_col = "Away"

    if row_home is not None and row_away is not None and home_col and away_col:
        home_mask = df[home_col].astype(str).apply(_normalize_team_key) == _normalize_team_key(row_home)
        away_mask = df[away_col].astype(str).apply(_normalize_team_key) == _normalize_team_key(row_away)
        mask = date_mask & home_mask & away_mask
    return mask


def _ensure_columns(df, columns):
    out = df.copy() if df is not None else pd.DataFrame()
    for col in columns:
        if col not in out.columns:
            out[col] = pd.NA
    return out


def _load_all_sheets(filename):
    if not os.path.exists(filename):
        return {}
    try:
        xl = pd.ExcelFile(filename)
        return {sheet: pd.read_excel(filename, sheet_name=sheet) for sheet in xl.sheet_names}
    except Exception:
        return {}


def _save_all_sheets(filename, sheets):
    with pd.ExcelWriter(filename, engine="openpyxl", mode="w") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)


def _format_line_value(val):
    try:
        num = float(val)
    except Exception:
        return None
    if abs(num - int(num)) < 1e-9:
        return str(int(num))
    return str(num).rstrip("0").rstrip(".")


def _is_blank_value(val):
    if val is None:
        return True
    try:
        if pd.isna(val):
            return True
    except Exception:
        pass
    if isinstance(val, str) and val.strip() == "":
        return True
    return False


def normalize_selection(selection):
    if selection is None:
        return None
    s = re.sub(r"\s+", " ", str(selection).strip())
    low = s.lower()
    if low.startswith("over"):
        m = re.search(r"over\s*([0-9]+(?:\.[0-9]+)?)", low)
        return f"Over {_format_line_value(m.group(1))}" if m else None
    if low.startswith("under"):
        m = re.search(r"under\s*([0-9]+(?:\.[0-9]+)?)", low)
        return f"Under {_format_line_value(m.group(1))}" if m else None
    if "hdp" in low:
        m = re.search(r"hdp\s*([+-]?[0-9]+(?:\.[0-9]+)?)", low)
        if not m:
            return None
        line = float(m.group(1))
        if line > 0:
            return f"HDP +{_format_line_value(line)}"
        if line < 0:
            return f"HDP {_format_line_value(line)}"
        return "HDP 0"
    return s


def evaluate_bet_outcome(selected_bet, actual_score, actual_result):
    bet = str(selected_bet or "").strip().lower()
    if not bet or bet == "nan":
        return "Pending"
    if bet == NO_BET_LABEL.lower():
        return "No Bet"
    if not isinstance(actual_score, str) or "-" not in actual_score:
        return "Pending"

    try:
        h, a = [int(x) for x in actual_score.split("-", 1)]
    except Exception:
        return "Pending"

    total = h + a
    res = str(actual_result or "").strip().lower()

    if bet.startswith("over"):
        val = float(bet.split("over", 1)[1].strip().split(" ")[0])
        return "Won" if total > val else "Lost"
    if bet.startswith("under"):
        val = float(bet.split("under", 1)[1].strip().split(" ")[0])
        return "Won" if total < val else "Lost"
    if bet.startswith("hdp"):
        m = re.search(r"hdp\s*([+-]?[0-9]+(?:\.[0-9]+)?)", bet)
        if not m:
            return "Pending"
        hdp = float(m.group(1))
        adj = (h - a) + hdp
        if adj > 0:
            return "Won"
        if adj < 0:
            return "Lost"
        return "Push"
    if "draw" in bet:
        return "Won" if res == "draw" else "Lost"
    if "away" in bet and "win" in bet:
        return "Won" if res == "away" else "Lost"
    if "home" in bet and "win" in bet:
        return "Won" if res == "home" else "Lost"
    return "Pending"


def _parse_score_pair(score):
    if score is None:
        return None
    text = str(score).strip()
    if not text:
        return None
    m = re.match(r"^\s*(\d+)\s*[-:]\s*(\d+)\s*$", text)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _safe_num(value, default=None):
    try:
        out = float(value)
        if pd.isna(out):
            return default
        return out
    except Exception:
        return default


def _recency_weight(date_val, max_date, half_life_days=120.0):
    try:
        d = pd.to_datetime(date_val, errors="coerce")
        if pd.isna(d) or pd.isna(max_date):
            return 1.0
        age_days = max(0.0, (max_date - d).days)
        return float(0.5 ** (age_days / max(1.0, half_life_days)))
    except Exception:
        return 1.0


def _clip(value, low, high):
    return max(low, min(high, value))


def _normalize_1x2_probs(home, draw, away):
    vals = [
        max(0.0, _safe_num(home, 0.0) or 0.0),
        max(0.0, _safe_num(draw, 0.0) or 0.0),
        max(0.0, _safe_num(away, 0.0) or 0.0),
    ]
    s = sum(vals)
    if s <= 0.0:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    if s > 3.0:
        vals = [v / 100.0 for v in vals]
        s = sum(vals)
    if s <= 0.0:
        return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
    return (vals[0] / s, vals[1] / s, vals[2] / s)


def _safe_mean(values):
    clean = [float(v) for v in values if v is not None]
    if not clean:
        return None
    return float(sum(clean) / len(clean))


def _round_metric_dict(metrics, digits=4):
    out = {}
    for key, val in metrics.items():
        if isinstance(val, float):
            out[key] = round(val, digits)
        else:
            out[key] = val
    return out


def _result_from_score_pair(score_pair):
    if score_pair is None:
        return None
    h, a = score_pair
    if h > a:
        return "Home"
    if h < a:
        return "Away"
    return "Draw"


def _aggregate_eval_records(records):
    n = len(records)
    if n == 0:
        return {"n_matches": 0}

    metrics = {
        "n_matches": int(n),
        "result_accuracy": _safe_mean([r.get("result_correct") for r in records]),
        "brier_1x2": _safe_mean([r.get("brier") for r in records]),
        "log_loss_1x2": _safe_mean([r.get("logloss") for r in records]),
        "exact_score_accuracy": _safe_mean([r.get("exact_score") for r in records]),
        "score_mae": _safe_mean([r.get("score_mae") for r in records]),
        "goal_diff_mae": _safe_mean([r.get("goal_diff_abs") for r in records]),
        "home_goal_mae": _safe_mean([r.get("home_goal_abs") for r in records]),
        "away_goal_mae": _safe_mean([r.get("away_goal_abs") for r in records]),
        "total_goals_mae": _safe_mean([r.get("total_goal_abs") for r in records]),
        "xg_mae": _safe_mean([r.get("xg_mae") for r in records]),
        "xg_rows": int(sum(1 for r in records if r.get("xg_mae") is not None)),
    }
    return _round_metric_dict(metrics, digits=4)


def _evaluate_prediction_rows(df):
    if df is None or df.empty:
        return {"overall": {"n_matches": 0}, "by_league": {}, "by_pred_result": {}, "by_actual_result": {}}

    records = []
    idx_map = {"Home": 0, "Draw": 1, "Away": 2}
    eps = 1e-12

    for _, row in df.iterrows():
        actual_score_pair = _parse_score_pair(row.get("Actual_Score"))
        actual_result = str(row.get("Actual_Result", "")).strip().title()
        if actual_result not in {"Home", "Draw", "Away"}:
            actual_result = _result_from_score_pair(actual_score_pair)
        if actual_result not in {"Home", "Draw", "Away"}:
            continue

        p_home, p_draw, p_away = _normalize_1x2_probs(
            row.get("Pred_Home_Win%"),
            row.get("Pred_Draw%"),
            row.get("Pred_Away_Win%"),
        )
        probs = [p_home, p_draw, p_away]

        pred_result = str(row.get("Pred_Result", "")).strip().title()
        if pred_result not in {"Home", "Draw", "Away"}:
            pred_result = ["Home", "Draw", "Away"][int(max(range(3), key=lambda i: probs[i]))]

        y = [0.0, 0.0, 0.0]
        y[idx_map[actual_result]] = 1.0
        brier = sum((probs[i] - y[i]) ** 2 for i in range(3))
        logloss = -math.log(max(eps, probs[idx_map[actual_result]]))
        result_correct = 1.0 if pred_result == actual_result else 0.0

        pred_score_pair = _parse_score_pair(row.get("Pred_Score"))
        home_goal_abs = away_goal_abs = total_goal_abs = score_mae = goal_diff_abs = exact_score = None
        if pred_score_pair is not None and actual_score_pair is not None:
            ph, pa = pred_score_pair
            ah, aa = actual_score_pair
            home_goal_abs = abs(float(ph) - float(ah))
            away_goal_abs = abs(float(pa) - float(aa))
            total_goal_abs = abs(float((ph + pa) - (ah + aa)))
            score_mae = (home_goal_abs + away_goal_abs) / 2.0
            goal_diff_abs = abs(float((ph - pa) - (ah - aa)))
            exact_score = 1.0 if (ph == ah and pa == aa) else 0.0

        exp_h_raw = _first_nonblank(row, ["Expected_Goals_Home", "xG_Home", "XG_Home"])
        exp_a_raw = _first_nonblank(row, ["Expected_Goals_Away", "xG_Away", "XG_Away"])
        exp_h = _safe_num(exp_h_raw, None)
        exp_a = _safe_num(exp_a_raw, None)
        xg_mae = None
        if exp_h is not None and exp_a is not None and actual_score_pair is not None:
            ah, aa = actual_score_pair
            xg_mae = (abs(exp_h - float(ah)) + abs(exp_a - float(aa))) / 2.0

        records.append(
            {
                "league": str(row.get("League", "")).strip() or "Unknown",
                "pred_result": pred_result,
                "actual_result": actual_result,
                "result_correct": result_correct,
                "brier": brier,
                "logloss": logloss,
                "exact_score": exact_score,
                "score_mae": score_mae,
                "goal_diff_abs": goal_diff_abs,
                "home_goal_abs": home_goal_abs,
                "away_goal_abs": away_goal_abs,
                "total_goal_abs": total_goal_abs,
                "xg_mae": xg_mae,
            }
        )

    overall = _aggregate_eval_records(records)

    def grouped(key):
        buckets = {}
        for rec in records:
            buckets.setdefault(rec.get(key), []).append(rec)
        out = {}
        for group_name, rows in buckets.items():
            out[str(group_name)] = _aggregate_eval_records(rows)
        return out

    return {
        "overall": overall,
        "by_league": grouped("league"),
        "by_pred_result": grouped("pred_result"),
        "by_actual_result": grouped("actual_result"),
    }


def _evaluate_quality_gates(overall_metrics, gates=None):
    cfg = dict(QUALITY_GATES if gates is None else gates)
    out = {
        "passed": False,
        "min_completed_matches": int(cfg.get("min_completed_matches", 30)),
        "checks": {},
    }

    n = int(overall_metrics.get("n_matches", 0) or 0)
    enough = n >= out["min_completed_matches"]
    out["checks"]["min_completed_matches"] = {
        "status": "pass" if enough else "fail",
        "value": n,
        "threshold": out["min_completed_matches"],
        "operator": ">=",
    }

    def check(metric_key, threshold_key, operator):
        val = overall_metrics.get(metric_key)
        threshold = cfg.get(threshold_key)
        if threshold is None:
            return {"status": "skipped", "value": val, "threshold": None, "operator": operator}
        if val is None:
            return {"status": "insufficient_data", "value": None, "threshold": threshold, "operator": operator}
        passed = bool(val >= threshold) if operator == ">=" else bool(val <= threshold)
        return {
            "status": "pass" if passed else "fail",
            "value": round(float(val), 4),
            "threshold": threshold,
            "operator": operator,
        }

    out["checks"]["result_accuracy"] = check("result_accuracy", "result_accuracy_min", ">=")
    out["checks"]["brier_1x2"] = check("brier_1x2", "brier_1x2_max", "<=")
    out["checks"]["log_loss_1x2"] = check("log_loss_1x2", "log_loss_1x2_max", "<=")
    out["checks"]["score_mae"] = check("score_mae", "score_mae_max", "<=")
    out["checks"]["xg_mae"] = check("xg_mae", "xg_mae_max", "<=")

    required = [k for k, v in out["checks"].items() if v.get("status") in {"pass", "fail"}]
    out["passed"] = enough and all(out["checks"][k]["status"] == "pass" for k in required if k != "min_completed_matches")
    return out

def _build_new_prediction_row(data):
    expected_home = round(float(data.get("Expected_Goals_Home", 0)), 2)
    expected_away = round(float(data.get("Expected_Goals_Away", 0)), 2)
    return {
        "Date": data.get("Date", ""),
        "League": data.get("League", ""),
        "Home": data.get("Home_Team", ""),
        "Away": data.get("Away_Team", ""),
        "Home%": round(float(data.get("Pred_Home_Win", 0)), 1),
        "Draw%": round(float(data.get("Pred_Draw", 0)), 1),
        "Away%": round(float(data.get("Pred_Away_Win", 0)), 1),
        "Pred_Score": data.get("Pred_Score", ""),
        "Pred_Result": data.get("Pred_Result", ""),
        "xG_Home": expected_home,
        "xG_Away": expected_away,
        "Expected_Goals_Home": expected_home,
        "Expected_Goals_Away": expected_away,
        "Actual_Score": None,
        "Actual_Result": None,
        "Correct": None,
        "Notes": None,
    }


def _build_calibration_from_predictions(df):
    if df is None or df.empty:
        return None
    if "Actual_Score" not in df.columns:
        return None

    done = df[df["Actual_Score"].notna() & (df["Actual_Score"].astype(str).str.strip() != "")].copy()
    if done.empty:
        return None

    date_series = pd.to_datetime(done.get("Date"), errors="coerce")
    max_date = date_series.max()

    league_acc = {}
    team_acc = {}
    used_rows = 0

    for _, row in done.iterrows():
        actual = _parse_score_pair(row.get("Actual_Score"))
        pred_score = _parse_score_pair(row.get("Pred_Score"))
        if actual is None:
            continue

        exp_h_raw = _first_nonblank(row, ["Expected_Goals_Home", "xG_Home", "XG_Home"])
        exp_a_raw = _first_nonblank(row, ["Expected_Goals_Away", "xG_Away", "XG_Away"])
        exp_h = _safe_num(exp_h_raw, None)
        exp_a = _safe_num(exp_a_raw, None)
        if exp_h is None or exp_a is None:
            if pred_score is None:
                continue
            exp_h = float(pred_score[0])
            exp_a = float(pred_score[1])

        ah, aa = actual
        res_h = float(ah) - float(exp_h)
        res_a = float(aa) - float(exp_a)

        weight = _recency_weight(row.get("Date"), max_date=max_date, half_life_days=120.0)
        league = str(row.get("League", "")).strip() or "Unknown"
        home_team = str(_first_nonblank(row, ["Home_Team", "Home"]) or "").strip()
        away_team = str(_first_nonblank(row, ["Away_Team", "Away"]) or "").strip()

        l = league_acc.setdefault(league, {"home_sum": 0.0, "away_sum": 0.0, "w": 0.0, "n": 0})
        l["home_sum"] += res_h * weight
        l["away_sum"] += res_a * weight
        l["w"] += weight
        l["n"] += 1

        if home_team:
            t = team_acc.setdefault(home_team, {"attack_sum": 0.0, "defense_sum": 0.0, "w": 0.0, "n": 0})
            t["attack_sum"] += res_h * weight
            t["defense_sum"] += res_a * weight
            t["w"] += weight
            t["n"] += 1

        if away_team:
            t = team_acc.setdefault(away_team, {"attack_sum": 0.0, "defense_sum": 0.0, "w": 0.0, "n": 0})
            t["attack_sum"] += res_a * weight
            t["defense_sum"] += res_h * weight
            t["w"] += weight
            t["n"] += 1

        used_rows += 1

    if used_rows == 0:
        return None

    total_home = total_away = total_w = 0.0
    total_n = 0
    by_league = {}
    for league, stats in league_acc.items():
        w = max(1e-9, stats["w"])
        home_res = stats["home_sum"] / w
        away_res = stats["away_sum"] / w
        league_rel = _clip(stats["n"] / 12.0, 0.0, 1.0)
        raw_home_scale = _clip(1.0 + (0.08 * home_res), 0.90, 1.10)
        raw_away_scale = _clip(1.0 + (0.08 * away_res), 0.90, 1.10)
        home_scale = 1.0 + ((raw_home_scale - 1.0) * league_rel)
        away_scale = 1.0 + ((raw_away_scale - 1.0) * league_rel)
        by_league[league] = {
            "n_matches": int(stats["n"]),
            "weighted_home_goal_residual": round(home_res, 4),
            "weighted_away_goal_residual": round(away_res, 4),
            "home_scale": round(home_scale, 4),
            "away_scale": round(away_scale, 4),
            "reliability": round(league_rel, 3),
        }
        total_home += stats["home_sum"]
        total_away += stats["away_sum"]
        total_w += stats["w"]
        total_n += stats["n"]

    by_team = {}
    for team, stats in team_acc.items():
        w = max(1e-9, stats["w"])
        attack_res = stats["attack_sum"] / w
        defense_res = stats["defense_sum"] / w
        reliability = _clip(stats["n"] / 8.0, 0.0, 1.0)
        attack_scale = 1.0 + (0.10 * attack_res * reliability)
        defense_scale = 1.0 + (0.10 * defense_res * reliability)
        by_team[team] = {
            "n_matches": int(stats["n"]),
            "weighted_attack_residual": round(attack_res, 4),
            "weighted_defense_residual": round(defense_res, 4),
            "attack_scale": round(_clip(attack_scale, 0.90, 1.12), 4),
            "defense_scale": round(_clip(defense_scale, 0.90, 1.12), 4),
            "reliability": round(reliability, 3),
        }

    by_team = dict(
        sorted(by_team.items(), key=lambda kv: kv[1].get("n_matches", 0), reverse=True)
    )

    g_w = max(1e-9, total_w)
    global_home_res = total_home / g_w
    global_away_res = total_away / g_w
    global_rel = _clip(total_n / 30.0, 0.0, 1.0)
    raw_home_scale = _clip(1.0 + (0.08 * global_home_res), 0.90, 1.10)
    raw_away_scale = _clip(1.0 + (0.08 * global_away_res), 0.90, 1.10)
    global_home_scale = 1.0 + ((raw_home_scale - 1.0) * global_rel)
    global_away_scale = 1.0 + ((raw_away_scale - 1.0) * global_rel)

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_rows_used": int(used_rows),
        "global": {
            "n_matches": int(total_n),
            "weighted_home_goal_residual": round(global_home_res, 4),
            "weighted_away_goal_residual": round(global_away_res, 4),
            "home_scale": round(global_home_scale, 4),
            "away_scale": round(global_away_scale, 4),
            "reliability": round(global_rel, 3),
        },
        "by_league": by_league,
        "by_team": by_team,
        "notes": [
            "Residual = actual goals - expected goals from latest_prediction.",
            "If Expected_Goals_* missing, fallback uses Pred_Score as rough proxy.",
            "Team scales are reliability-weighted and clipped to avoid overfitting.",
        ],
    }


def build_model_calibration(filename="prediction_tracker.xlsx", output_file=CALIBRATION_FILE):
    if not os.path.exists(filename):
        print(f"{filename} not found.")
        return
    try:
        df = pd.read_excel(filename, sheet_name="Predictions", engine="openpyxl")
    except Exception as e:
        print(f"Could not read Predictions sheet: {e}")
        return

    calibration = _build_calibration_from_predictions(df)
    if not calibration:
        print("[Info] No verified rows available for calibration yet.")
        return

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(calibration, f, indent=4, ensure_ascii=False)

    g = calibration["global"]
    print(f"[Info] Calibration saved to {output_file}")
    print(
        "[Info] Global residuals "
        f"H={g['weighted_home_goal_residual']:+.3f}, "
        f"A={g['weighted_away_goal_residual']:+.3f} "
        f"-> scales H={g['home_scale']:.3f}, A={g['away_scale']:.3f}"
    )


def evaluate_model_performance(filename="prediction_tracker.xlsx", output_file=PERFORMANCE_FILE):
    if not os.path.exists(filename):
        print(f"{filename} not found.")
        return

    try:
        df = pd.read_excel(filename, sheet_name="Predictions", engine="openpyxl")
    except Exception as e:
        print(f"Could not read Predictions sheet: {e}")
        return

    metrics = _evaluate_prediction_rows(df)
    overall = metrics.get("overall", {})
    gates = _evaluate_quality_gates(overall)

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_file": filename,
        "overall": overall,
        "quality_gates": gates,
        "by_league": metrics.get("by_league", {}),
        "by_pred_result": metrics.get("by_pred_result", {}),
        "by_actual_result": metrics.get("by_actual_result", {}),
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)

    overall_rows = []
    metric_labels = {
        "n_matches": "n_matches",
        "result_accuracy": "result_accuracy",
        "brier_1x2": "brier_1x2",
        "log_loss_1x2": "log_loss_1x2",
        "exact_score_accuracy": "exact_score_accuracy",
        "score_mae": "score_mae",
        "goal_diff_mae": "goal_diff_mae",
        "home_goal_mae": "home_goal_mae",
        "away_goal_mae": "away_goal_mae",
        "total_goals_mae": "total_goals_mae",
        "xg_mae": "xg_mae",
        "xg_rows": "xg_rows",
    }
    for key in metric_labels:
        overall_rows.append(
            {
                "Section": "overall",
                "Metric": metric_labels[key],
                "Value": overall.get(key),
            }
        )
    for gate_name, gate in gates.get("checks", {}).items():
        overall_rows.append(
            {
                "Section": "quality_gate",
                "Metric": gate_name,
                "Value": gate.get("status"),
                "Threshold": gate.get("threshold"),
                "Current": gate.get("value"),
                "Operator": gate.get("operator"),
            }
        )
    overall_rows.append(
        {
            "Section": "quality_gate",
            "Metric": "overall_passed",
            "Value": bool(gates.get("passed")),
        }
    )
    df_overall = pd.DataFrame(overall_rows)

    league_rows = []
    for league, m in (metrics.get("by_league") or {}).items():
        row = {"League": league}
        row.update(m)
        league_rows.append(row)
    df_league = pd.DataFrame(league_rows).sort_values(by="n_matches", ascending=False) if league_rows else pd.DataFrame()

    seg_rows = []
    for group_name, group_metrics in (metrics.get("by_pred_result") or {}).items():
        row = {"Segment_Type": "pred_result", "Segment": group_name}
        row.update(group_metrics)
        seg_rows.append(row)
    for group_name, group_metrics in (metrics.get("by_actual_result") or {}).items():
        row = {"Segment_Type": "actual_result", "Segment": group_name}
        row.update(group_metrics)
        seg_rows.append(row)
    df_segments = pd.DataFrame(seg_rows).sort_values(by=["Segment_Type", "n_matches"], ascending=[True, False]) if seg_rows else pd.DataFrame()

    sheets = _load_all_sheets(filename)
    sheets["Model Eval"] = df_overall
    sheets["Model Eval League"] = df_league
    sheets["Model Eval Segments"] = df_segments
    backup_tracker(filename)
    _save_all_sheets(filename, sheets)

    print(f"[Info] Performance report saved to {output_file}")
    print(
        "[Info] Overall metrics "
        f"n={overall.get('n_matches', 0)}, "
        f"acc={overall.get('result_accuracy')}, "
        f"brier={overall.get('brier_1x2')}, "
        f"logloss={overall.get('log_loss_1x2')}, "
        f"score_mae={overall.get('score_mae')} "
        f"| gates_passed={gates.get('passed')}"
    )


def close_loop_after_actual(filename="prediction_tracker.xlsx"):
    update_bet_results(filename=filename)
    build_model_calibration(filename=filename, output_file=CALIBRATION_FILE)
    evaluate_model_performance(filename=filename, output_file=PERFORMANCE_FILE)
    print("[Info] Close loop complete: update_bets -> calibrate -> evaluate")


def _build_bet_data_row(data):
    bet_data = data.get("Bet_Data", {})
    if not bet_data:
        return None

    def pct(val):
        return round(float(val) * 100.0, 1)

    return {
        "Date": data.get("Date", ""),
        "Match": data.get("Match", ""),
        "League": data.get("League", ""),
        "HDP -3": pct(bet_data.get("HDP_-3", 0.0)),
        "HDP -2": pct(bet_data.get("HDP_-2", 0.0)),
        "HDP -1": pct(bet_data.get("HDP_-1", 0.0)),
        "HDP 0": pct(bet_data.get("HDP_0", 0.0)),
        "HDP +1": pct(bet_data.get("HDP_1", 0.0)),
        "HDP +2": pct(bet_data.get("HDP_2", 0.0)),
        "HDP +3": pct(bet_data.get("HDP_3", 0.0)),
        "Over 0.5": pct(bet_data.get("Over_0.5", 0.0)),
        "Under 0.5": pct(bet_data.get("Under_0.5", 0.0)),
        "Over 1.5": pct(bet_data.get("Over_1.5", 0.0)),
        "Under 1.5": pct(bet_data.get("Under_1.5", 0.0)),
        "Over 2.5": pct(bet_data.get("Over_2.5", 0.0)),
        "Under 2.5": pct(bet_data.get("Under_2.5", 0.0)),
        "Over 3.5": pct(bet_data.get("Over_3.5", 0.0)),
        "Under 3.5": pct(bet_data.get("Under_3.5", 0.0)),
    }


def _best_bet_from_model(data):
    bet_data = data.get("Bet_Data", {})
    bet_detail = data.get("Bet_Detail", {})
    if not bet_data:
        return None

    candidates = []

    for boundary in [1.5, 2.5, 3.5]:
        for side in ["Over", "Under"]:
            key = f"{side}_{boundary}"
            if key in bet_data:
                candidates.append((f"{side} {boundary}", float(bet_data[key])))

    for hdp in [-1, 0, 1]:
        key = f"HDP_{hdp}"
        if key in bet_detail:
            win = float(bet_detail[key].get("win", 0.0))
            push = float(bet_detail[key].get("push", 0.0))
        else:
            win = float(bet_data.get(key, 0.0))
            push = 0.0
        prob = win / max(1e-9, 1.0 - push)
        label = f"HDP {hdp}" if hdp <= 0 else f"HDP +{hdp}"
        candidates.append((label, prob))

    if not candidates:
        return None

    # Sort by probability descending first
    candidates.sort(key=lambda x: x[1], reverse=True)

    # --- Logic for "Investable" / Value Bets ---
    # Prioritize specific lines if they have decent probability (> 60%)
    # Preference Order: Over 2.5 (High Value) > HDP (Money Line/Asian) > Over 1.5 (Safe)
    
    preferred_bet = None
    
    # 1. Check Over/Under 2.5 (Mental Threshold ~60-65%)
    for label, prob in candidates:
        if "2.5" in label and prob >= 0.60:
            preferred_bet = (label, prob)
            break
            
    # 2. If no 2.5, check HDP (Handicaps)
    if not preferred_bet:
        for label, prob in candidates:
            if "HDP" in label and prob >= 0.60:
                # Prefer Main HDP (usually around 0, -0.5, -1 for value) - simplified here to any preferred HDP
                preferred_bet = (label, prob)
                break
    
    # 3. If still nothing, fallback to highest probability (usually Over 1.5 or 0.5)
    best_label, best_prob = preferred_bet if preferred_bet else candidates[0]

    confidence = "High" if best_prob >= 0.70 else "Medium" if best_prob >= 0.60 else "Low"
    return {
        "Date": data.get("Date", ""),
        "Match": data.get("Match", ""),
        "Selected_Bet": best_label,
        "Confidence": confidence,
        "Reasoning": f"Model-only selection by highest probability {best_prob:.3f}.",
        "Actual_Score": None,
        "Bet_Result": None,
        "Odds": None,
        "Implied_Prob": None,
        "Model_Prob": round(best_prob, 4),
        "Edge": None,
        "EV": None,
        "Rule_Tier": "model_only_best_prob",
    }


def save_new_prediction():
    json_file = "latest_prediction.json"
    excel_file = "prediction_tracker.xlsx"

    if not os.path.exists(json_file):
        print(f"Error: {json_file} not found.")
        return

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Loading prediction: {data.get('Match', 'Unknown')}")
    new_row = _build_new_prediction_row(data)

    sheets = _load_all_sheets(excel_file)
    df_pred = sheets.get("Predictions", pd.DataFrame())
    df_pred = _ensure_columns(df_pred, list(new_row.keys()))

    match_label = f"{new_row['Home']} vs {new_row['Away']}"
    dup = _duplicate_mask(df_pred, new_row["Date"], match_label, new_row["Home"], new_row["Away"])
    if dup.any():
        preserve_cols = {
            "Actual_Score",
            "Actual_Result",
            "Correct",
            "Notes",
        }
        for col, val in new_row.items():
            if col in preserve_cols and _is_blank_value(val):
                continue
            df_pred.loc[dup, col] = val
        print("[Info] Updated existing Predictions row.")
    else:
        df_pred = pd.concat([df_pred, pd.DataFrame([new_row])], ignore_index=True)
        print("[Info] Added row to Predictions.")
    sheets["Predictions"] = df_pred

    backup_tracker(excel_file)
    _save_all_sheets(excel_file, sheets)
    print(f"Saved prediction to {excel_file}")

def calculate_summary_stats(filename="prediction_tracker.xlsx"):
    if not os.path.exists(filename):
        return
    try:
        df = pd.read_excel(filename, sheet_name="Predictions", engine="openpyxl")
    except Exception:
        return

    if "Actual_Result" not in df.columns:
        return

    completed = df[df["Actual_Result"].notna() & (df["Actual_Result"].astype(str).str.strip() != "")].copy()
    total = len(completed)

    if total == 0:
        summary_df = pd.DataFrame(
            {
                "Metric": ["Total Verified Matches", "Result Accuracy (%)"],
                "Value": [0, 0.0],
            }
        )
    else:
        correct_col = pd.to_numeric(completed.get("Correct"), errors="coerce").fillna(0.0)
        summary_df = pd.DataFrame(
            {
                "Metric": [
                    "Total Verified Matches",
                    "Correct Results",
                    "Result Accuracy (%)",
                ],
                "Value": [
                    total,
                    int(correct_col.sum()),
                    round(float(correct_col.mean() * 100.0), 2),
                ],
            }
        )

    sheets = _load_all_sheets(filename)
    sheets["Summary"] = summary_df
    backup_tracker(filename)
    _save_all_sheets(filename, sheets)
    print("[Info] Summary updated.")


def clean_duplicates(filename="prediction_tracker.xlsx"):
    if not os.path.exists(filename):
        print(f"{filename} not found.")
        return

    sheets = _load_all_sheets(filename)
    for sheet in ["Predictions", "bet data", "bet predic"]:
        if sheet not in sheets or sheets[sheet].empty:
            continue
        df = sheets[sheet].copy()
        date_key = pd.to_datetime(df.get("Date", pd.Series([""] * len(df))), errors="coerce")
        date_key = date_key.dt.strftime("%Y-%m-%d").where(date_key.notna(), df.get("Date", "").astype(str).str.slice(0, 10))

        if "Home_Team" in df.columns and "Away_Team" in df.columns:
            key = (
                date_key.astype(str)
                + "|"
                + df["Home_Team"].astype(str).apply(_normalize_team_key)
                + "|"
                + df["Away_Team"].astype(str).apply(_normalize_team_key)
            )
        else:
            key = date_key.astype(str) + "|" + df.get("Match", "").astype(str).apply(_normalize_text_key)

        before = len(df)
        df["__key"] = key
        df = df.drop_duplicates(subset=["__key"], keep="last").drop(columns=["__key"])
        sheets[sheet] = df
        removed = before - len(df)
        if removed > 0:
            print(f"[Info] {sheet}: removed {removed} duplicates")

    backup_tracker(filename)
    _save_all_sheets(filename, sheets)
    calculate_summary_stats(filename)


def update_bet_results(filename="prediction_tracker.xlsx"):
    if not os.path.exists(filename):
        print(f"{filename} not found.")
        return

    sheets = _load_all_sheets(filename)
    df_pred = sheets.get("Predictions", pd.DataFrame())
    df_bet = sheets.get("bet predic", pd.DataFrame())

    if df_pred.empty or df_bet.empty:
        print("No data to update bet results.")
        return

    for col in ["Actual_Score", "Bet_Result"]:
        if col not in df_bet.columns:
            df_bet[col] = pd.Series([pd.NA] * len(df_bet), dtype="object")
        else:
            df_bet[col] = df_bet[col].astype("object")

    results = {}
    for _, row in df_pred.iterrows():
        score = row.get("Actual_Score")
        result = row.get("Actual_Result")
        if pd.isna(score) or str(score).strip() == "":
            continue
        key = (_normalize_date_key(row.get("Date")), _normalize_text_key(row.get("Match")))
        results[key] = (str(score), str(result))

    updated = 0
    for i, row in df_bet.iterrows():
        key = (_normalize_date_key(row.get("Date")), _normalize_text_key(row.get("Match")))
        if key not in results:
            continue
        score_str, result_str = results[key]
        status = evaluate_bet_outcome(row.get("Selected_Bet"), score_str, result_str)
        if status != "Pending":
            df_bet.at[i, "Actual_Score"] = score_str
            df_bet.at[i, "Bet_Result"] = status
            updated += 1

    sheets["bet predic"] = df_bet
    backup_tracker(filename)
    _save_all_sheets(filename, sheets)
    calculate_summary_stats(filename)
    print(f"[Info] Updated {updated} bet rows.")


def _calculate_ev(probability, decimal_odds):
    if not probability or not decimal_odds:
        return None
    try:
        p = float(probability)
        o = float(decimal_odds)
        if o <= 1.0: return None
        # EV = (Probability * (Odds - 1)) - ((1 - Probability) * 1)
        # Simplified: (P * O) - 1
        ev = (p * o) - 1.0
        return round(ev * 100.0, 2)  # Return as percentage
    except Exception:
        return None


def update_bet_ev(filename="prediction_tracker.xlsx", odds_file="odds_input.csv"):
    if not os.path.exists(filename):
        print(f"{filename} not found.")
        return
    
    # helper to normalize match names for matching
    def norm_key(date_val, match_val):
        return (_normalize_date_key(date_val), _normalize_text_key(match_val))

    # Read Odds
    if not os.path.exists(odds_file):
        print(f"{odds_file} not found. Cannot calculate EV without odds.")
        return
    
    try:
        df_odds = pd.read_csv(odds_file)
    except Exception as e:
        print(f"Error reading {odds_file}: {e}")
        return

    sheets = _load_all_sheets(filename)
    df_predic = sheets.get("bet predic", pd.DataFrame())
    
    if df_predic.empty:
        print("No 'bet predic' data found to match with odds.")
        return

    # Create map from prediction tracker
    # Key: (Date, Match) -> { 'Model_Prob': ..., 'Selected_Bet': ... }
    pred_map = {}
    for i, row in df_predic.iterrows():
        k = norm_key(row.get("Date"), row.get("Match"))
        pred_map[k] = {
            "Model_Prob": row.get("Model_Prob"),
            "Selected_Bet": row.get("Selected_Bet"),
            "Confidence": row.get("Confidence"),
            "League": row.get("League", "") # Might be in Predictions, but let's try
        }
        # If League is missing in bet predic, we might need to look it up in Predictions
        # But for 'bet ev' sheet, we just need the basics + EV.

    ev_rows = []
    
    # Iterate through odds input
    # We match odds input to our predictions
    matched_count = 0
    
    for _, row in df_odds.iterrows():
        # Clean inputs
        date_str = str(row.get("Date", "")).strip()
        match_str = str(row.get("Match", "")).strip()
        selection = str(row.get("Selection", "")).strip()
        odds_val = row.get("Odds")
        
        k = norm_key(date_str, match_str)
        
        if k in pred_map:
            # We found a match in our tracker
            pred_info = pred_map[k]
            model_sel = str(pred_info.get("Selected_Bet", "")).strip()
            
            # Use fuzzy check or direct check if the odds selection matches the model selection
            # Simple check: is the selection string contained in model selection or vice versa?
            # Or assume the user inputted odds FOR the selected bet.
            # For now, let's assume valid input in CSV corresponds to the 'Selected_Bet'.
            # Or we can check if 'Selection' matches 'Selected_Bet' loosely
            
            # Logic: If Selection is valid and Odds is valid
            prob = pred_info.get("Model_Prob")
            ev = _calculate_ev(prob, odds_val)
            
            new_row = {
                "Date": date_str,
                "Match": match_str,
                "Selection": selection, # User input selection
                "Model_Selection": model_sel,
                "Model_Prob": prob,
                "Odds": odds_val,
                "EV%": ev,
                "Confidence": pred_info.get("Confidence"),
                "Notes": "Matched" if ev is not None else "Invalid Odds/Prob"
            }
            ev_rows.append(new_row)
            matched_count += 1
            
            # OPTIONAL: Update 'bet predic' sheet with these odds and EV too?
            # The user asked for 'bet ev' sheet specifically in the past context (implied by README check)
            # README says: bet ev sheet exists.
            
    if not ev_rows:
        print("No matches found between odds_input.csv and prediction_tracker.xlsx")
        # Ensure sheet exists at least
        if "bet ev" not in sheets:
            sheets["bet ev"] = pd.DataFrame(columns=["Date", "Match", "Selection", "Model_Selection", "Model_Prob", "Odds", "EV%", "Confidence", "Notes"])
    else:
        df_ev = pd.DataFrame(ev_rows)
        # Merge with existing 'bet ev' to avoid wiping history?
        # Implementation: Append new ones, update existing? 
        # For simplicity: Re-build or Append. README doesn't specify history policy for this sheet.
        # Let's Append.
        
        current_ev = sheets.get("bet ev", pd.DataFrame())
        current_ev = _ensure_columns(current_ev, list(ev_rows[0].keys()))
        
        # Deduplicate based on Date+Match+Selection
        df_ev = pd.concat([current_ev, df_ev], ignore_index=True)
        # Simple dedupe
        df_ev["__key"] = df_ev["Date"].astype(str) + "|" + df_ev["Match"].astype(str) + "|" + df_ev["Selection"].astype(str)
        df_ev = df_ev.drop_duplicates(subset=["__key"], keep="last").drop(columns=["__key"])
        
        sheets["bet ev"] = df_ev
        print(f"[Info] Updated 'bet ev' sheet with {matched_count} entries.")

    backup_tracker(filename)
    _save_all_sheets(filename, sheets)


def update_prediction_with_result():
    print("No hardcoded updater in rebuilt version.")
    print("Fill Actual_Score/Actual_Result manually in Predictions, then run:")
    print("python update_tracker.py update_bets")
    print("or python update_tracker.py close_loop")


if __name__ == "__main__":
    if len(os.sys.argv) > 1:
        cmd = os.sys.argv[1].strip().lower()
        if cmd == "save":
            save_new_prediction()
            calculate_summary_stats()
        elif cmd == "clean":
            clean_duplicates()
        elif cmd == "update_bets":
            update_bet_results()
        elif cmd == "update_ev":
            update_bet_ev()
        elif cmd == "calibrate":
            build_model_calibration()
        elif cmd == "evaluate":
            evaluate_model_performance()
        elif cmd == "close_loop":
            close_loop_after_actual()
        else:
            print("Usage: python update_tracker.py [save|clean|update_bets|update_ev|calibrate|evaluate|close_loop]")
    else:
        update_prediction_with_result()
        calculate_summary_stats()
