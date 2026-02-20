import argparse
import json
import math
import os
import sys
from datetime import datetime

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import analyze_match


def _safe_float(value, default=0.0):
    try:
        out = float(value)
        if math.isnan(out) or math.isinf(out):
            return float(default)
        return out
    except Exception:
        return float(default)


def _parse_score(score):
    text = str(score or "").strip()
    if "-" not in text:
        return None
    try:
        left, right = text.split("-", 1)
        return int(left.strip()), int(right.strip())
    except Exception:
        return None


def _result_index_from_score(score_pair):
    if score_pair is None:
        return None
    h, a = score_pair
    if h > a:
        return 0
    if h == a:
        return 1
    return 2


def _normalize_probs(sim):
    if not isinstance(sim, dict):
        return None
    vals = [
        max(0.0, _safe_float(sim.get("home_win_prob"), 0.0)),
        max(0.0, _safe_float(sim.get("draw_prob"), 0.0)),
        max(0.0, _safe_float(sim.get("away_win_prob"), 0.0)),
    ]
    total = sum(vals)
    if total <= 0.0:
        return None
    if total > 3.0:
        vals = [v / 100.0 for v in vals]
        total = sum(vals)
    if total <= 0.0:
        return None
    return [vals[0] / total, vals[1] / total, vals[2] / total]


def _evaluate_one(sim, actual_score_pair):
    probs = _normalize_probs(sim)
    actual_idx = _result_index_from_score(actual_score_pair)
    if probs is None or actual_idx is None:
        return None

    eps = 1e-12
    y = [0.0, 0.0, 0.0]
    y[actual_idx] = 1.0
    brier = sum((probs[i] - y[i]) ** 2 for i in range(3))
    logloss = -math.log(max(eps, probs[actual_idx]))
    calibration_gap = abs(1.0 - probs[actual_idx])

    pred_score = _parse_score(sim.get("most_likely_score"))
    score_mae = None
    if pred_score is not None:
        ph, pa = pred_score
        ah, aa = actual_score_pair
        score_mae = (abs(float(ph) - float(ah)) + abs(float(pa) - float(aa))) / 2.0

    return {
        "brier_1x2": brier,
        "log_loss_1x2": logloss,
        "calibration_gap": calibration_gap,
        "score_mae": score_mae,
    }


def _aggregate(records):
    if not records:
        return {"n_matches": 0}

    def _mean(key):
        vals = [r[key] for r in records if r.get(key) is not None]
        if not vals:
            return None
        return float(sum(vals) / len(vals))

    return {
        "n_matches": int(len(records)),
        "brier_1x2": round(_mean("brier_1x2"), 4) if _mean("brier_1x2") is not None else None,
        "log_loss_1x2": round(_mean("log_loss_1x2"), 4) if _mean("log_loss_1x2") is not None else None,
        "calibration_gap": round(_mean("calibration_gap"), 4) if _mean("calibration_gap") is not None else None,
        "score_mae": round(_mean("score_mae"), 4) if _mean("score_mae") is not None else None,
    }


def _resolve_fixture_row(row):
    home = str(row.get("Home_Team") or row.get("Home") or "").strip()
    away = str(row.get("Away_Team") or row.get("Away") or "").strip()
    league = str(row.get("League") or "").strip()
    return home, away, league


def run_backtest(tracker_path, output_json, max_rows=None):
    df = pd.read_excel(tracker_path, sheet_name="Predictions", engine="openpyxl")
    if "Actual_Score" not in df.columns:
        raise RuntimeError("Predictions sheet missing Actual_Score column.")

    done = df[df["Actual_Score"].notna() & (df["Actual_Score"].astype(str).str.strip() != "")].copy()
    if done.empty:
        raise RuntimeError("No completed matches found in tracker.")

    done["__date"] = pd.to_datetime(done.get("Date"), errors="coerce")
    done = done.sort_values(by="__date", kind="stable").reset_index(drop=True)
    if max_rows is not None and max_rows > 0:
        done = done.tail(int(max_rows)).reset_index(drop=True)

    records_by_model = {"v9": [], "demo_v2": [], "hybrid": []}
    rolling_rows = []

    for i, row in done.iterrows():
        actual_score = _parse_score(row.get("Actual_Score"))
        if actual_score is None:
            continue

        home, away, league = _resolve_fixture_row(row)
        if not home or not away:
            continue

        stats_league = analyze_match.find_team_league(home) or analyze_match.find_team_league(away) or "Premier_League"
        model_league = league or stats_league

        home_sim_stats = analyze_match.get_simulation_stats(home, stats_league)
        away_sim_stats = analyze_match.get_simulation_stats(away, stats_league)
        home_prog = analyze_match.get_progression_stats(home, stats_league)
        away_prog = analyze_match.get_progression_stats(away, stats_league)
        home_flow = analyze_match.get_game_flow_stats(home, model_league)
        away_flow = analyze_match.get_game_flow_stats(away, model_league)

        bundle = analyze_match._resolve_core_predictions(
            home=home,
            away=away,
            stats_league=stats_league,
            home_sim_stats=home_sim_stats,
            away_sim_stats=away_sim_stats,
            home_prog=home_prog,
            away_prog=away_prog,
            context_text="",
            home_flow=home_flow,
            away_flow=away_flow,
        )

        sim_v9 = bundle.get("v9_sim")
        sim_hybrid = bundle.get("hybrid_sim")
        sim_demo = analyze_match._demo_v2_to_sim_result(bundle.get("demo_v2_shadow"), sim_v9=sim_v9)

        model_sims = {
            "v9": sim_v9,
            "demo_v2": sim_demo,
            "hybrid": sim_hybrid,
        }
        for model_name, sim in model_sims.items():
            metrics = _evaluate_one(sim, actual_score)
            if metrics is not None:
                rec = {"date": str(row.get("Date") or ""), "match": f"{home} vs {away}"}
                rec.update(metrics)
                records_by_model[model_name].append(rec)

        rolling_rows.append(
            {
                "index": int(i + 1),
                "date": str(row.get("Date") or ""),
                "match": f"{home} vs {away}",
                "v9": _aggregate(records_by_model["v9"]),
                "demo_v2": _aggregate(records_by_model["demo_v2"]),
                "hybrid": _aggregate(records_by_model["hybrid"]),
            }
        )

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tracker_path": tracker_path,
        "rows_evaluated": int(len(rolling_rows)),
        "overall": {
            "v9": _aggregate(records_by_model["v9"]),
            "demo_v2": _aggregate(records_by_model["demo_v2"]),
            "hybrid": _aggregate(records_by_model["hybrid"]),
        },
        "rolling_origin": rolling_rows,
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)
    return payload


def main():
    parser = argparse.ArgumentParser(description="Rolling-origin backtest for MODEL_CORE variants (v9/demo_v2/hybrid).")
    parser.add_argument("--tracker", default="prediction_tracker.xlsx", help="Path to prediction tracker Excel file.")
    parser.add_argument(
        "--output",
        default="model_backtest_rolling_origin.json",
        help="Path to output JSON report.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional limit to evaluate latest N completed matches only.",
    )
    args = parser.parse_args()

    report = run_backtest(
        tracker_path=args.tracker,
        output_json=args.output,
        max_rows=args.max_rows,
    )
    overall = report.get("overall", {})
    print("[Info] Rolling-origin backtest complete.")
    print(
        "[Info] Overall metrics "
        f"v9={overall.get('v9')} | "
        f"demo_v2={overall.get('demo_v2')} | "
        f"hybrid={overall.get('hybrid')}"
    )
    print(f"[Info] Saved report to {args.output}")


if __name__ == "__main__":
    main()
