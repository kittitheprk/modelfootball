# Upgrade Plan: V10 Reliable Football Prediction Platform

Status: Active draft  
Owner: Pending  
Last updated: 2026-02-20

## Progress Snapshot (2026-02-20)

Completed in this iteration:
- Baseline commit frozen before V10 work.
- `MODEL_CORE` router implemented (`v9 | demo_v2 | hybrid`, default `v9`).
- `demo_v2` adapter hardened (league/team resolution, unit policy, source confidence context).
- Hybrid lambda blending implemented with bounded clipping and decomposition logs.
- Tactical regime calibration hooks added (`by_regime`) across simulator + tracker calibration build.
- Rolling-origin comparison script added: `scripts/backtest_model_cores.py`.
- Report appendix expanded to compare `v9`, `demo_v2`, `hybrid` with delta 1X2/xG and confidence class.
- New tests added for router, adapter units, hybrid stability, and prediction schema regression.

Remaining:
- Refresh calibration artifact from latest tracker data and review regime buckets.
- Final validation pass on full command set and tracker integration in real run.

## 1) Vision

Build a trustworthy pre-match prediction platform that optimizes long-run probability quality, not one-match hit rate.

Target outputs:
- `P(scoreline)` from a full score matrix
- `P(Home/Draw/Away)` from the same distribution surface
- calibrated confidence that can be audited over time

Compatibility goals:
- no breaking change to `latest_prediction.json` in initial rollout
- keep `simulator_v9` as immediate fallback path

## 2) Baseline Already Added From This Chat

These are now part of the production baseline and must be preserved in V10:

- Tactical layer connected end-to-end (`PPDA`, `Field Tilt`, `Directness`, `High Error`, `BigChanceDiff`) to adjust expected goals.
- Tactical context exposed for traceability (`Simulator_Tactical_Context` and flow payloads).
- `home_flow` and `away_flow` are now passed from `analyze_match.py` into the simulator.
- Regression test added for tactical adjustment behavior in `tests/test_simulator_v9.py`.

## 3) V10 Core Architecture (Hybrid)

V10 should be a hybrid, layered model:

1. Data layer  
- match logs, team stats, game flow, progression proxies, player/lineup context, optional OPTA aggregates

2. Feature layer  
- tactical (`PPDA`, `Field Tilt`, transition/directness)
- progression (`xT` proxy, deep completion, counter index)
- squad state (lineup quality, missing players, fatigue/load)

3. Lambda layer  
- estimate `lambda_home`, `lambda_away` from combined signals
- keep each adjustment bounded and logged

4. Distribution layer  
- Dixon-Coles score matrix with dynamic `rho`

5. Calibration layer  
- global + league + team + tactical-regime calibration

6. Decision/output layer  
- publish 1X2, scoreline, bet surfaces, and full explanation context

## 4) Reliability Principles

- Time-safe only: no feature can use future information.
- No leakage: split by match date, never random split for model selection.
- Bounded adjustments: each layer capped to prevent unstable overreaction.
- Graceful fallback: missing tactical/lineup inputs must degrade to stable defaults.
- Auditability first: every prediction stores adjustment decomposition.

## 5) Data Contracts and Quality Controls

Standardization policy:
- canonical team name map across all sources
- explicit unit policy (`raw`, `per_match`, `per_90`) with transformation metadata
- source confidence score for each critical feature group

Pre-run checks:
- fixture/context alignment (`Match`, `League`, team names)
- minimum usable data thresholds for tactical and progression features
- schema checks before pipeline run

Operational checks:
- retain `scripts/system_check.py` and pipeline preflight as mandatory gates
- keep backup and tracker integrity checks before writes

## 6) Modeling Strategy (V10)

Primary path:
- keep `simulator_v9` statistical base and tactical decomposition
- improve tactical weighting by league and sample reliability
- keep dynamic `rho` in Dixon-Coles and extend with regime-aware calibration

Upgrade path from `demo_model_v2`:
- use `demo_model_v2` modules to produce alternative lambda estimates
- run in shadow mode first (`v9` primary, `demo_v2` observer)
- compare and blend only after passing acceptance gates

Target blend design:
- `lambda = base_strength + progression + tactical + lineup + fatigue + calibration`
- each term logged and clipped with per-league bounds

## 7) Evaluation and Calibration Framework

Mandatory validation method:
- rolling-origin backtest by date
- league-wise and season-phase segmentation

Primary model quality metrics:
- `Brier Score (1X2)`
- `Log Loss (1X2)`
- calibration curve / reliability gap

Secondary monitoring metrics:
- score MAE
- goal-difference MAE
- exact-score accuracy (diagnostic only)

Calibration hierarchy:
- global
- by league
- by team
- by tactical regime (pressing-high, low-block, transition-heavy)

## 8) Explainability and Traceability Requirements

Every prediction should include:
- base xG values
- tactical, progression, lineup, fatigue, calibration adjustments
- final `lambda_home`, `lambda_away`, and `rho`
- key positional battles and tactical scenario summary

Persistable artifacts:
- `latest_prediction.json`
- `model_calibration.json`
- `model_performance.json`
- tracker evaluation sheets

## 9) Migration Phases (Safe Rollout)

Phase 0: Baseline freeze  
- snapshot current outputs and metrics for fixed fixture set

Phase 1: Adapter + shadow mode  
- connect `demo_model_v2` via adapter, no user-facing switch

Phase 2: Unit-audit and feature parity  
- verify unit correctness and schema parity across all feature groups

Phase 3: Controlled A/B in production  
- feature flag switch by runtime config (`MODEL_CORE=v9|demo_v2|hybrid`)

Phase 4: Promotion criteria  
- promote only when reliability metrics improve without stability regression

Phase 5: Continuous monitoring  
- drift alerts, periodic recalibration, rollback-ready deployment

## 10) Acceptance Criteria Before V10 Default

- No schema regression in `latest_prediction.json`
- No increase in failure rate for prediction pipeline
- Better or equal rolling backtest metrics vs baseline:
- `Brier Score` non-inferior and target improvement trend
- `Log Loss` non-inferior and target improvement trend
- Stable calibration by league and team segments
- End-to-end health checks and test suite pass

## 11) Rollback Plan

- keep `MODEL_CORE=v9` path always available
- config-only rollback within one deploy
- retain shadow comparison logs for post-incident review

## 12) Immediate Next Actions

1. Add explicit feature flag and model-core router.
2. Build adapter from current schema to `demo_model_v2` inputs.
3. Add rolling-origin evaluation script for side-by-side (`v9` vs `demo_v2` vs `hybrid`).
4. Add tactical-regime calibration table to `model_calibration.json`.
5. Add reliability report section (per league, per regime, per confidence bucket).
