import math
import numpy as np


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _clip(value, low, high):
    return max(low, min(high, value))


def _poisson_pmf(k, lam):
    if k < 0:
        return 0.0
    lam = max(1e-9, float(lam))
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _build_score_matrix(lambda_home, lambda_away, max_goals=10, rho=-0.07):
    # Independent Poisson base
    home_probs = np.array([_poisson_pmf(i, lambda_home) for i in range(max_goals + 1)])
    away_probs = np.array([_poisson_pmf(i, lambda_away) for i in range(max_goals + 1)])
    mat = np.outer(home_probs, away_probs)

    # Dixon-Coles low-score correction
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


def simulate_match(home_xg, away_xg, home_sofascore=None, away_sofascore=None, iterations=10000):
    """
    Simulator v8 (Accuracy-first)
    - Uses blended xG + goals-per-90 features.
    - Applies conservative shrinkage to reduce overconfident tails.
    - Uses Dixon-Coles correction for low-score realism.
    - Keeps output schema backward-compatible with v7.1.
    """
    # 1) Signals from xG
    h_att = _safe_float(home_xg.get("attack", {}).get("xg_per_game"), 1.25)
    h_def = _safe_float(home_xg.get("defense", {}).get("xga_per_game"), 1.20)
    a_att = _safe_float(away_xg.get("attack", {}).get("xg_per_game"), 1.25)
    a_def = _safe_float(away_xg.get("defense", {}).get("xga_per_game"), 1.20)

    xg_home = (h_att + a_def) / 2.0
    xg_away = (a_att + h_def) / 2.0

    # 2) Goals/90 signal (if available)
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

    base_home = w_xg * xg_home + w_goals * goals_home
    base_away = w_xg * xg_away + w_goals * goals_away

    # 3) Conservative shrinkage to avoid overconfidence
    prior_home, prior_away = 1.35, 1.20
    shr = 0.86
    reg_home = shr * base_home + (1 - shr) * prior_home
    reg_away = shr * base_away + (1 - shr) * prior_away

    # 4) Dynamic adjustments: home, form, and strength
    home_adv, away_dis = 1.04, 0.98
    h_form = _safe_float(home_xg.get("form_last_5"), 7.5)
    a_form = _safe_float(away_xg.get("form_last_5"), 7.5)
    form_adj = _clip(((h_form - a_form) / 15.0) * 0.08, -0.04, 0.04)

    strength_raw = math.log((reg_home + 0.05) / (reg_away + 0.05))
    strength_adj = _clip(math.tanh(strength_raw) * 0.06, -0.06, 0.06)

    lambda_home = reg_home * home_adv * (1.0 + form_adj + strength_adj)
    lambda_away = reg_away * away_dis * (1.0 - form_adj - strength_adj)

    lambda_home = _clip(lambda_home, 0.25, 3.8)
    lambda_away = _clip(lambda_away, 0.25, 3.8)

    # 5) Dixon-Coles rho: stronger in balanced games, weaker in mismatches
    close = _clip(1.0 - abs(strength_raw) / 1.2, 0.0, 1.0)
    rho = -0.03 - (0.07 * close)

    # 6) Probability matrix
    prob_matrix = _build_score_matrix(lambda_home, lambda_away, max_goals=10, rho=rho)

    home_win_prob = float(np.tril(prob_matrix, k=-1).sum() * 100)
    draw_prob = float(np.trace(prob_matrix) * 100)
    away_win_prob = float(np.triu(prob_matrix, k=1).sum() * 100)

    top3 = _top_scores(prob_matrix, top_n=3)
    best = top3[0]
    most_likely_score = f"{best[0]}-{best[1]}"
    top3_scores = ", ".join([f"{h}-{a} ({p*100:.1f}%)" for h, a, p in top3])

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
        "bonus_applied": (
            f"HomeAdv x{home_adv:.2f} | Form {form_adj*100:+.1f}% | "
            f"Strength {strength_adj*100:+.1f}% | DC rho {rho:.3f}"
        ),
        "model_version": "v8"
    }


if __name__ == "__main__":
    # Quick sanity check
    h_xg = {"attack": {"xg_per_game": 1.6}, "defense": {"xga_per_game": 1.1}, "form_last_5": 10}
    a_xg = {"attack": {"xg_per_game": 1.4}, "defense": {"xga_per_game": 1.3}, "form_last_5": 7}
    sim = simulate_match(h_xg, a_xg, None, None)
    print(sim)
