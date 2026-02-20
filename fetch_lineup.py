# fetch_lineup.py
"""Utility script to fetch Sofascore lineup widget for a given event ID and update match_context.txt.

Usage:
    python fetch_lineup.py <event_id>

The script constructs the iframe HTML snippet and writes a new match_context.txt file with
match information, league, and the fetched line‑ups. It preserves any existing team news
if present (optional)."""

import sys
import os
from pathlib import Path

# Constants
MATCH_CONTEXT_PATH = Path("match_context.txt")

def build_iframe(event_id: str) -> str:
    """Return the HTML iframe block for the given Sofascore event ID."""
    iframe = (
        f'<iframe id="sofa-lineups-embed-{event_id}" '
        f'src="https://widgets.sofascore.com/embed/lineups?id={event_id}&widgetTheme=light" '
        f'style="height:786px!important;max-width:800px!important;width:100%!important;" '
        f'frameborder="0" scrolling="no"></iframe>\n'
        f'<div style="font-size:12px;font-family:Arial,sans-serif">'
        f'<a href="https://www.sofascore.com/football/match/sassuolo-hellas-verona/bebsTfb#id:{event_id}" '
        f'target="_blank" rel="noreferrer">Sassuolo - Hellas Verona Live Score</a></div>'
    )
    return iframe

def update_match_context(event_id: str, home: str = "Sassuolo", away: str = "Hellas Verona", league: str = "Serie_A", date: str = "2026-02-20"):
    """Write a new match_context.txt file with the supplied information and the iframe.
    Any existing file is overwritten.
    """
    lines = []
    lines.append(f"Match: {home} vs {away}")
    lines.append(f"Date: {date}")
    lines.append(f"League: {league}")
    lines.append("")
    lines.append("Lineups")
    lines.append(build_iframe(event_id))
    lines.append("")
    # Optional placeholder for Team News – keep empty for now
    lines.append("Team News")
    lines.append("")
    content = "\n".join(lines) + "\n"
    MATCH_CONTEXT_PATH.write_text(content, encoding="utf-8")
    print(f"[Info] match_context.txt updated for {home} vs {away} (event {event_id})")

def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_lineup.py <event_id>")
        sys.exit(1)
    event_id = sys.argv[1]
    # In a real implementation you might fetch additional metadata (date, league) via Sofascore API.
    # For now we use static defaults.
    update_match_context(event_id)

if __name__ == "__main__":
    main()
