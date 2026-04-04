#!/usr/bin/env python3
"""Run engine-vs-engine matches and measure Elo difference.

Usage:
    python bench/run_match.py --games 20 --depth 3
    python bench/run_match.py --games 50 --depth 4 --opponent stockfish
"""

import argparse
import subprocess
import sys
import chess
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class UCIEngine:
    """Manage a UCI engine subprocess."""

    def __init__(self, command: list[str]):
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
        self._send("isready")
        self._wait_for("readyok")

    def _send(self, cmd: str):
        self.process.stdin.write(cmd + "\n")
        self.process.stdin.flush()

    def _wait_for(self, target: str, timeout: float = 30.0) -> str:
        """Read lines until we see one starting with target."""
        start = time.time()
        lines = []
        while time.time() - start < timeout:
            line = self.process.stdout.readline().strip()
            lines.append(line)
            if line.startswith(target):
                return line
        raise TimeoutError(f"Timeout waiting for '{target}'. Got: {lines}")

    def new_game(self):
        self._send("ucinewgame")
        self._send("isready")
        self._wait_for("readyok")

    def set_position(self, board: chess.Board):
        moves_str = " ".join(m.uci() for m in board.move_stack)
        if moves_str:
            self._send(f"position startpos moves {moves_str}")
        else:
            self._send("position startpos")

    def go(self, depth: int = None, movetime: int = None) -> chess.Move:
        if depth is not None:
            self._send(f"go depth {depth}")
        elif movetime is not None:
            self._send(f"go movetime {movetime}")
        else:
            self._send("go depth 3")

        line = self._wait_for("bestmove")
        move_str = line.split()[1]
        if move_str == "0000" or move_str == "(none)":
            return None
        return chess.Move.from_uci(move_str)

    def quit(self):
        try:
            self._send("quit")
            self.process.wait(timeout=5)
        except Exception:
            self.process.kill()


def play_game(
    engine1_cmd: list[str],
    engine2_cmd: list[str],
    depth: int = 3,
    max_moves: int = 200,
) -> str:
    """Play a single game. Returns '1-0', '0-1', or '1/2-1/2'."""
    e1 = UCIEngine(engine1_cmd)
    e2 = UCIEngine(engine2_cmd)

    try:
        e1.new_game()
        e2.new_game()
        board = chess.Board()

        for move_num in range(max_moves):
            if board.is_game_over():
                break

            engine = e1 if board.turn == chess.WHITE else e2
            engine.set_position(board)
            move = engine.go(depth=depth)

            if move is None or move not in board.legal_moves:
                # Engine failed to produce a legal move
                return "0-1" if board.turn == chess.WHITE else "1-0"

            board.push(move)

        result = board.result()
        if result == "*":
            return "1/2-1/2"  # Max moves reached
        return result

    finally:
        e1.quit()
        e2.quit()


def run_match(
    engine1_cmd: list[str],
    engine2_cmd: list[str],
    n_games: int = 20,
    depth: int = 3,
) -> dict:
    """Play n_games between two engines, alternating colors."""
    results = {"wins": 0, "losses": 0, "draws": 0, "games": []}

    for i in range(n_games):
        # Alternate colors
        if i % 2 == 0:
            white_cmd, black_cmd = engine1_cmd, engine2_cmd
            is_white = True
        else:
            white_cmd, black_cmd = engine2_cmd, engine1_cmd
            is_white = False

        print(f"Game {i + 1}/{n_games}...", end=" ", flush=True)
        result = play_game(white_cmd, black_cmd, depth=depth)
        print(result, flush=True)

        # Translate to engine1's perspective
        if result == "1-0":
            if is_white:
                results["wins"] += 1
            else:
                results["losses"] += 1
        elif result == "0-1":
            if is_white:
                results["losses"] += 1
            else:
                results["wins"] += 1
        else:
            results["draws"] += 1

        results["games"].append({"game": i + 1, "result": result, "engine1_white": is_white})

    return results


def estimate_elo_diff(wins: int, losses: int, draws: int) -> float:
    """Estimate Elo difference from match results."""
    import math
    total = wins + losses + draws
    if total == 0:
        return 0.0
    score = (wins + draws / 2) / total
    # Clamp to avoid log(0)
    score = max(0.001, min(0.999, score))
    return -400 * math.log10(1 / score - 1)


def main():
    parser = argparse.ArgumentParser(description="Run chess engine matches")
    parser.add_argument("--games", type=int, default=20, help="Number of games")
    parser.add_argument("--depth", type=int, default=3, help="Search depth")
    parser.add_argument(
        "--engine",
        default=f"{sys.executable} run.py",
        help="Engine 1 command (default: our engine)",
    )
    parser.add_argument(
        "--opponent",
        default=f"{sys.executable} run.py",
        help="Engine 2 command (default: self-play)",
    )
    args = parser.parse_args()

    engine1_cmd = args.engine.split()
    engine2_cmd = args.opponent.split()

    print(f"Match: {args.engine} vs {args.opponent}")
    print(f"Games: {args.games}, Depth: {args.depth}")
    print("=" * 40)

    results = run_match(engine1_cmd, engine2_cmd, args.games, args.depth)

    print("=" * 40)
    print(f"Results: +{results['wins']} -{results['losses']} ={results['draws']}")
    elo_diff = estimate_elo_diff(results["wins"], results["losses"], results["draws"])
    print(f"Estimated Elo difference: {elo_diff:+.0f}")

    # Save results
    from bench.elo_tracker import save_result
    save_result(
        opponent=args.opponent,
        games=args.games,
        wins=results["wins"],
        losses=results["losses"],
        draws=results["draws"],
        depth=args.depth,
    )


if __name__ == "__main__":
    main()
