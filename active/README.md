# Active Transforms

This folder is for non-raw processing scripts only.

- `convert_sofascore_per90.py`
  - Input: `sofascore_team_data/*_Team_Stats.xlsx` (raw)
  - Output: `active/sofascore_team_data/*_Team_Stats.xlsx` (derived with `*_per_90`)

Raw web scraping scripts remain outside this folder and should not create derived metrics.
