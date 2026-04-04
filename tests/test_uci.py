"""Integration tests for UCI protocol."""

import subprocess
import sys


def run_uci(commands: str, timeout: int = 10) -> str:
    """Send UCI commands to the engine and return output."""
    result = subprocess.run(
        [sys.executable, "run.py"],
        input=commands,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd="/home/user/cautious-pancake",
    )
    return result.stdout


def test_uci_handshake():
    output = run_uci("uci\nquit\n")
    assert "id name CautiousPancake" in output
    assert "id author" in output
    assert "uciok" in output


def test_isready():
    output = run_uci("uci\nisready\nquit\n")
    assert "readyok" in output


def test_position_startpos_and_go():
    output = run_uci("uci\nisready\nposition startpos\ngo depth 1\nquit\n")
    assert "bestmove" in output
    # Extract the move and verify it's valid UCI notation
    for line in output.strip().split("\n"):
        if line.startswith("bestmove"):
            move_str = line.split()[1]
            assert len(move_str) >= 4  # e.g., "e2e4"


def test_position_fen():
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    output = run_uci(f"uci\nisready\nposition fen {fen}\ngo depth 1\nquit\n")
    assert "bestmove" in output


def test_position_with_moves():
    output = run_uci(
        "uci\nisready\nposition startpos moves e2e4 e7e5\ngo depth 1\nquit\n"
    )
    assert "bestmove" in output


def test_ucinewgame():
    output = run_uci(
        "uci\nisready\nucinewgame\nposition startpos\ngo depth 1\nquit\n"
    )
    assert "bestmove" in output


def test_multiple_go_commands():
    output = run_uci(
        "uci\nisready\n"
        "position startpos\ngo depth 1\n"
        "position startpos moves e2e4\ngo depth 1\n"
        "quit\n"
    )
    bestmoves = [l for l in output.split("\n") if l.startswith("bestmove")]
    assert len(bestmoves) == 2
