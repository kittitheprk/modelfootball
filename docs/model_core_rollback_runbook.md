# MODEL_CORE Rollback Runbook

Last updated: 2026-02-20

## 1) Trigger Conditions

Rollback immediately if one or more happen after deploy:
- prediction pipeline failure rate increases
- `latest_prediction.json` schema break is observed
- reliability metrics degrade (Brier / LogLoss / calibration gap)
- demo adapter resolution fails for critical fixtures

## 2) Fast Rollback (Config Only)

Set runtime environment:

```powershell
$env:MODEL_CORE = "v9"
```

Then rerun:

```powershell
python analyze_match.py Arsenal Liverpool
```

Validation checklist:
- output file created: `latest_prediction.json`
- `Model_Core` equals `v9`
- no critical warnings from simulator path

## 3) Disable Hybrid Influence Only

If hybrid is active but demo contribution is unstable:

```powershell
$env:MODEL_CORE = "hybrid"
$env:HYBRID_DEMO_WEIGHT = "0.0"
```

This keeps hybrid route but effectively behaves as v9 lambda.

## 4) Disable demo_v2 Adapter Risk

If adapter unit resolution is unstable:

```powershell
$env:MODEL_CORE = "v9"
Remove-Item Env:DEMO_V2_UNIT_POLICY -ErrorAction SilentlyContinue
```

## 5) Post-Rollback Verification

Run:

```powershell
python -m unittest tests/test_simulator_v9.py tests/test_tactical_scenarios.py tests/test_demo_v2_appendix.py
python -m py_compile analyze_match.py simulator_v9.py
python analyze_match.py Arsenal Liverpool --target-score 1-1
```

Confirm:
- no test regressions
- output schema still backward compatible
- tracker save path still works (`python update_tracker.py save`)

## 6) Incident Notes Template

Record:
- deployment timestamp
- rollback timestamp
- active `MODEL_CORE` before/after
- failing fixture samples
- metric deltas (Brier, LogLoss, calibration gap, score MAE)
- next corrective action owner
