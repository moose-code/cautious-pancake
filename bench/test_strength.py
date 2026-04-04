#!/usr/bin/env python3
"""Quick strength test against Stockfish at a target Elo.

Usage:
    python bench/test_strength.py                    # Default: 10 games vs Stockfish @ 800 Elo
    python bench/test_strength.py --elo 1200         # Test against 1200-rated Stockfish
    python bench/test_strength.py --elo 600 --games 20
    python bench/test_strength.py --quick            # 4 fast games for a sanity check
"""

import argparse
import subprocess
import sys
import time
import chess
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STOCKFISH_PATH = "/usr/games/stockfish"


class UCIEngine:
    """Manage a UCI engine subprocess."""

    def __init__(self, command: list[str], options: dict[str, str] = None):
        self.name = command[0].split("/")[-1]
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        self._send("uci")
        self._wait_for("uciok")

        if options:
            for key, val in options.items():
                self._send(f"setoption name {key} value {val}")

        self._send("isready")
        self._wait_for("readyok")

    def _send(self, cmd: str):
        self.process.stdin.write(cmd + "\n")
        self.process.stdin.flush()

    def _wait_for(self, target: str, timeout: float = 30.0) -> str:
        start = time.time()
        lines = []
        while time.time() - start < timeout:
            line = self.process.stdout.readline().strip()
            lines.append(line)
            if line.startswith(target):
                return line
        raise TimeoutError(f"Timeout waiting for '{target}'")

    def new_game(self):
        self._send("ucinewgame")
        self._send("isready")
        self._wait_for("readyok")

    def set_position(self, moves: list[str]):
        if moves:
            self._send(f"position startpos moves {' '.join(moves)}")
        else:
            self._send("position startpos")

    def go(self, depth: int = None, movetime: int = None) -> str:
        if depth is not None:
            self._send(f"go depth {depth}")
        elif movetime is not None:
            self._send(f"go movetime {movetime}")
        else:
            self._send("go depth 4")
        line = self._wait_for("bestmove")
        return line.split()[1]

    def quit(self):
        try:
            self._send("quit")
            self.process.wait(timeout=3)
        except Exception:
            self.process.kill()


def play_game(our_cmd, sf_options, our_depth, sf_depth, our_is_white, max_moves=150):
    """Play one game. Returns result from OUR engine's perspective: 1.0, 0.5, 0.0"""
    our = UCIEngine(our_cmd)
    sf = UCIEngine([STOCKFISH_PATH], options=sf_options)

    try:
        our.new_game()
        sf.new_game()

        board = chess.Board()
        moves = []

        for _ in range(max_moves):
            if board.is_game_over():
                break

            is_our_turn = (board.turn == chess.WHITE) == our_is_white
            engine = our if is_our_turn else sf
            depth = our_depth if is_our_turn else sf_depth

            engine.set_position(moves)
            move_str = engine.go(depth=depth)

            if move_str in ("0000", "(none)"):
                break

            try:
                move = board.parse_uci(move_str)
                if move not in board.legal_moves:
                    # Illegal move = loss
                    return 0.0 if is_our_turn else 1.0
                board.push(move)
                moves.append(move_str)
            except ValueError:
                return 0.0 if is_our_turn else 1.0

        result = board.result()
        if result == "1-0":
            return 1.0 if our_is_white else 0.0
        elif result == "0-1":
            return 0.0 if our_is_white else 1.0
        else:
            return 0.5  # Draw or game not finished

    finally:
        our.quit()
        sf.quit()


def estimate_elo(score_pct: float, opponent_elo: int) -> int:
    """Estimate our Elo from score percentage against a known-Elo opponent."""
    if score_pct <= 0.001:
        score_pct = 0.001
    if score_pct >= 0.999:
        score_pct = 0.999
    elo_diff = -400 * math.log10(1 / score_pct - 1)
    return int(opponent_elo + elo_diff)


def main():
    parser = argparse.ArgumentParser(description="Test engine strength vs Stockfish")
    parser.add_argument("--elo", type=int, default=800, help="Stockfish target Elo (default: 800)")
    parser.add_argument("--games", type=int, default=10, help="Number of games (default: 10)")
    parser.add_argument("--depth", type=int, default=4, help="Our engine search depth (default: 4)")
    parser.add_argument("--sf-depth", type=int, default=4, help="Stockfish search depth (default: 4)")
    parser.add_argument("--quick", action="store_true", help="Quick test: 4 games, depth 3")
    args = parser.parse_args()

    if args.quick:
        args.games = 4
        args.depth = 3
        args.sf_depth = 2

    our_cmd = [sys.executable, "run.py"]
    sf_options = {
        "UCI_LimitStrength": "true",
        "UCI_Elo": str(args.elo),
        "Skill Level": str(max(0, min(20, (args.elo - 400) // 100))),
    }

    print(f"CautiousPancake (depth {args.depth}) vs Stockfish @ {args.elo} Elo (depth {args.sf_depth})")
    print(f"Playing {args.games} games...")
    print("=" * 50)

    wins = 0
    losses = 0
    draws = 0

    for i in range(args.games):
        our_is_white = (i % 2 == 0)
        color = "White" if our_is_white else "Black"
        print(f"  Game {i+1}/{args.games} (we play {color})...", end=" ", flush=True)

        score = play_game(our_cmd, sf_options, args.depth, args.sf_depth, our_is_white)

        if score == 1.0:
            wins += 1
            print("WIN", flush=True)
        elif score == 0.0:
            losses += 1
            print("LOSS", flush=True)
        else:
            draws += 1
            print("DRAW", flush=True)

    total = wins + losses + draws
    score_pct = (wins + draws * 0.5) / total
    est_elo = estimate_elo(score_pct, args.elo)

    print("=" * 50)
    print(f"Results: +{wins} -{losses} ={draws} ({score_pct:.1%})")
    print(f"Estimated Elo: ~{est_elo}")
    print()

    # Save to tracker
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from bench.elo_tracker import save_result
        save_result(
            opponent=f"stockfish-{args.elo}",
            games=total,
            wins=wins,
            losses=losses,
            draws=draws,
            depth=args.depth,
            notes=f"vs Stockfish UCI_Elo={args.elo}, sf_depth={args.sf_depth}",
        )
    except Exception as e:
        print(f"(Could not save result: {e})")

    return est_elo


if __name__ == "__main__":
    main()
