#!/usr/bin/env python3
"""Track and display Elo progression over time.

Results are stored in bench/results.json.
"""

import json
import math
import subprocess
from datetime import datetime
from pathlib import Path

RESULTS_FILE = Path(__file__).resolve().parent / "results.json"


def estimate_elo_diff(wins: int, losses: int, draws: int) -> float:
    """Estimate Elo difference from match results."""
    total = wins + losses + draws
    if total == 0:
        return 0.0
    score = (wins + draws / 2) / total
    score = max(0.001, min(0.999, score))
    return -400 * math.log10(1 / score - 1)


def get_git_commit() -> str:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def load_results() -> list[dict]:
    """Load existing results from file."""
    if RESULTS_FILE.exists():
        return json.loads(RESULTS_FILE.read_text())
    return []


def save_result(
    opponent: str,
    games: int,
    wins: int,
    losses: int,
    draws: int,
    depth: int,
    notes: str = "",
):
    """Save a match result to the results file."""
    results = load_results()
    elo_diff = estimate_elo_diff(wins, losses, draws)

    entry = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "commit": get_git_commit(),
        "opponent": opponent,
        "depth": depth,
        "games": games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "elo_diff": round(elo_diff, 1),
        "notes": notes,
    }

    results.append(entry)
    RESULTS_FILE.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nResult saved to {RESULTS_FILE}")
    return entry


def show_history():
    """Print Elo progression history."""
    results = load_results()
    if not results:
        print("No results yet. Run some matches first!")
        return

    print(f"\n{'Date':<20} {'Commit':<10} {'Opponent':<20} {'W-L-D':<12} {'Elo Diff':>10}")
    print("-" * 75)
    for r in results:
        date = r["date"][:16]
        wld = f"+{r['wins']} -{r['losses']} ={r['draws']}"
        print(f"{date:<20} {r['commit']:<10} {r['opponent'][:20]:<20} {wld:<12} {r['elo_diff']:>+10.0f}")


if __name__ == "__main__":
    show_history()
