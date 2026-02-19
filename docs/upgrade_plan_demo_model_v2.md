# Upgrade Note: Integrate `demo_model_v2` into Current Analysis Project

Status: Draft note (implementation deferred)
Owner: Pending
Last updated: 2026-02-20

## 1) Goal

Prepare a safe upgrade path to reuse `demo_model_v2` as an improved prediction core while keeping current production flow stable.

Current production entrypoints:
- `analyze_match.py`
- `update_tracker.py`
- `update_football_data.py`

Candidate modules from `demo_model_v2`:
- `demo_model_v2/data_loader.py`
- `demo_model_v2/feature_engine.py`
- `demo_model_v2/match_log_loader.py`
- `demo_model_v2/player_impact_engine.py`
- `demo_model_v2/poisson_model.py`
- `demo_model_v2/simulator.py`
- `demo_model_v2/backtest.py`

## 2) Non-goals (for first rollout)

- No breaking change to `latest_prediction.json` schema.
- No removal of `simulator_v9` path in first release.
- No direct replacement of all data pipelines in one step.

## 3) Key risks to control

- Unit mismatch (`raw`, `per match`, `per 90`) across sources.
- Team naming mismatch across datasets.
- Metric drift after swapping model core.
- Silent degradation in bet outputs or tracker metrics.

## 4) Safe migration strategy (phased)

Phase 0: Baseline freeze
- Keep current production as reference.
- Save baseline outputs for a fixed match set:
- `latest_prediction.json`
- `model_performance.json`
- `model_calibration.json`

Phase 1: Adapter layer only
- Build an adapter from current data format to `demo_model_v2` inputs.
- Run `demo_model_v2` in shadow mode (no user-facing switch yet).
- Compare outputs against production and log deltas.

Phase 2: Unit audit mode (read-only)
- Add explicit unit checks before any conversion.
- Detect if metric is already `*_per_90`; do not re-normalize.
- If only raw exists, compute from `raw / matches`.
- Write warnings only, no auto-correction in this phase.

Phase 3: Controlled correction mode
- Enable auto-correction only for fields with deterministic rules.
- Keep fallback to old behavior for uncertain cases.
- Keep a feature flag to disable new logic instantly.

Phase 4: Gradual production switch
- Add runtime switch:
- `MODEL_CORE=v9` (default)
- `MODEL_CORE=demo_v2` (opt-in)
- Promote to default only after acceptance criteria are met.

## 5) Unit policy for critical fields

Target fields to standardize:
- goals scored
- goals conceded
- shots on target
- key passes
- expected goals
- expected assists (xA proxy path)

Rules:
- Prefer explicit `*_per_90` if present.
- Else compute from raw totals and matches played.
- Never divide again if value already looks normalized and source label confirms per-90.
- Persist source and transformation path in debug metadata.

## 6) Proposed integration points

In `analyze_match.py`:
- Keep current output schema.
- Add optional branch:
- current branch -> `simulator_v9`
- new branch -> adapter -> `demo_model_v2` core
- Record branch used in `Model_Version` and debug context.

In `update_tracker.py`:
- No schema break.
- Ensure evaluation uses robust fallback columns (`Expected_Goals_*` and `xG_*`).

In pipeline:
- Keep `update_football_data.py` unchanged for initial rollout.
- Add optional validation step script for unit audit reports.

## 7) Acceptance criteria before default switch

- Prediction run success rate: no regression.
- No schema regression in `latest_prediction.json`.
- No unresolved `null` from avoidable unit issues.
- Backtest metrics not worse than baseline by agreed thresholds.
- Health checks and tests pass:
- `python scripts/system_check.py`
- `python -m unittest tests/test_automation_paths.py tests/test_full_system.py tests/test_simulator_v9.py`

## 8) Rollback plan

- Keep `MODEL_CORE=v9` as immediate fallback.
- Keep adapter isolated so rollback is config-only, not code rewrite.
- Keep shadow comparison logs for incident review.

## 9) Implementation backlog (deferred)

- Add `MODEL_CORE` feature flag.
- Build `demo_model_v2` adapter module.
- Add unit-audit report script.
- Add regression comparison script (`v9` vs `demo_v2`).
- Add tests for unit detection and conversion guards.

## 10) Next action when resuming work

Start with Phase 1 and Phase 2 together:
- Implement adapter (no behavior switch).
- Implement unit-audit warnings (read-only).
- Run shadow predictions on a fixed fixture set and compare.
