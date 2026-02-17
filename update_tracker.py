
import json
import os
import re
import shutil
import unicodedata
from datetime import datetime

import pandas as pd

NO_BET_LABEL = "No Bet"
TEAM_SUFFIX_TOKENS = {"fc", "cf", "sc", "afc", "ac"}


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

    if row_home is not None and row_away is not None and "Home_Team" in df.columns and "Away_Team" in df.columns:
        home_mask = df["Home_Team"].astype(str).apply(_normalize_team_key) == _normalize_team_key(row_home)
        away_mask = df["Away_Team"].astype(str).apply(_normalize_team_key) == _normalize_team_key(row_away)
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

def _build_new_prediction_row(data):
    qc_raw = data.get("QC_Flags", "")
    if isinstance(qc_raw, list):
        qc_text = " | ".join(str(x) for x in qc_raw)
    else:
        qc_text = "" if qc_raw is None else str(qc_raw)

    ctx = data.get("Context_Header", {})
    if isinstance(ctx, dict):
        ctx_text = "; ".join([f"{k}={v}" for k, v in ctx.items() if v])
    else:
        ctx_text = str(ctx or "")

    return {
        "Date": data.get("Date", ""),
        "Match": data.get("Match", ""),
        "Match_Canonical": data.get("Match_Canonical", data.get("Match", "")),
        "League": data.get("League", ""),
        "Home_Team": data.get("Home_Team", ""),
        "Away_Team": data.get("Away_Team", ""),
        "Home_Team_Canonical": data.get("Home_Team_Canonical", ""),
        "Away_Team_Canonical": data.get("Away_Team_Canonical", ""),
        "Pred_Home_Win%": data.get("Pred_Home_Win", ""),
        "Pred_Draw%": data.get("Pred_Draw", ""),
        "Pred_Away_Win%": data.get("Pred_Away_Win", ""),
        "Pred_Score": data.get("Pred_Score", ""),
        "Pred_Result": data.get("Pred_Result", ""),
        "Pred_Score_Unconditional": data.get("Pred_Score_Unconditional", ""),
        "Pred_Result_1X2": data.get("Pred_Result_1X2", data.get("Pred_Result", "")),
        "Pred_Result_From_Score": data.get("Pred_Result_From_Score", ""),
        "QC_Flags": qc_text,
        "Context_Header": ctx_text,
        "Actual_Score": None,
        "Actual_Result": None,
        "Result_Correct": None,
        "Score_Correct": None,
        "Goal_Diff_Error": None,
        "Notes": None,
    }


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
    bet_row = _build_bet_data_row(data)
    predic_row = _best_bet_from_model(data)

    sheets = _load_all_sheets(excel_file)
    df_pred = sheets.get("Predictions", pd.DataFrame())
    df_pred = _ensure_columns(df_pred, list(new_row.keys()))

    dup = _duplicate_mask(df_pred, new_row["Date"], new_row["Match"], new_row["Home_Team"], new_row["Away_Team"])
    if dup.any():
        for col, val in new_row.items():
            df_pred.loc[dup, col] = val
        print("[Info] Updated existing Predictions row.")
    else:
        df_pred = pd.concat([df_pred, pd.DataFrame([new_row])], ignore_index=True)
        print("[Info] Added row to Predictions.")
    sheets["Predictions"] = df_pred

    if bet_row is not None:
        df_bet = sheets.get("bet data", pd.DataFrame())
        df_bet = _ensure_columns(df_bet, list(bet_row.keys()))
        dup_bet = _duplicate_mask(df_bet, bet_row["Date"], bet_row["Match"])
        if dup_bet.any():
            for col, val in bet_row.items():
                df_bet.loc[dup_bet, col] = val
            print("[Info] Updated existing bet data row.")
        else:
            df_bet = pd.concat([df_bet, pd.DataFrame([bet_row])], ignore_index=True)
            print("[Info] Added row to bet data.")
        sheets["bet data"] = df_bet

    if predic_row is not None:
        df_predic = sheets.get("bet predic", pd.DataFrame())
        df_predic = _ensure_columns(df_predic, list(predic_row.keys()))
        dup_predic = _duplicate_mask(df_predic, predic_row["Date"], predic_row["Match"])
        if dup_predic.any():
            for col, val in predic_row.items():
                df_predic.loc[dup_predic, col] = val
            print("[Info] Updated existing bet predic row.")
        else:
            df_predic = pd.concat([df_predic, pd.DataFrame([predic_row])], ignore_index=True)
            print("[Info] Added row to bet predic.")
        sheets["bet predic"] = df_predic

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
                "Metric": ["Total Verified Matches", "Result Accuracy (%)", "Exact Score Accuracy (%)", "Avg Goal Diff Error"],
                "Value": [0, 0.0, 0.0, 0.0],
            }
        )
    else:
        completed["Result_Correct"] = pd.to_numeric(completed.get("Result_Correct"), errors="coerce").fillna(0.0)
        completed["Score_Correct"] = pd.to_numeric(completed.get("Score_Correct"), errors="coerce").fillna(0.0)
        gd = pd.to_numeric(completed.get("Goal_Diff_Error"), errors="coerce")
        summary_df = pd.DataFrame(
            {
                "Metric": [
                    "Total Verified Matches",
                    "Correct Result (W/D/L)",
                    "Result Accuracy (%)",
                    "Exact Score Correct",
                    "Exact Score Accuracy (%)",
                    "Avg Goal Diff Error",
                ],
                "Value": [
                    total,
                    int(completed["Result_Correct"].sum()),
                    round(float(completed["Result_Correct"].mean() * 100.0), 2),
                    int(completed["Score_Correct"].sum()),
                    round(float(completed["Score_Correct"].mean() * 100.0), 2),
                    round(float(gd.mean()), 2) if gd.notna().any() else 0.0,
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
        else:
            print("Usage: python update_tracker.py [save|clean|update_bets|update_ev]")
    else:
        update_prediction_with_result()
        calculate_summary_stats()
