"""UCI protocol implementation for CautiousPancake.

Handles stdin/stdout communication following the Universal Chess Interface spec.
"""

import sys
import chess
from engine.search import search

ENGINE_NAME = "CautiousPancake"
ENGINE_AUTHOR = "Claude Code"


def main():
    """Main UCI loop. Reads commands from stdin, writes responses to stdout."""
    board = chess.Board()

    while True:
        try:
            line = input().strip()
        except EOFError:
            break

        if not line:
            continue

        tokens = line.split()
        cmd = tokens[0]

        if cmd == "uci":
            print(f"id name {ENGINE_NAME}", flush=True)
            print(f"id author {ENGINE_AUTHOR}", flush=True)
            # Options can be added here later (e.g. Hash, Threads)
            print("uciok", flush=True)

        elif cmd == "isready":
            print("readyok", flush=True)

        elif cmd == "ucinewgame":
            board = chess.Board()

        elif cmd == "position":
            board = _parse_position(tokens)

        elif cmd == "go":
            depth = _parse_go_depth(tokens)
            move = search(board, depth=depth)
            if move is not None:
                print(f"bestmove {move.uci()}", flush=True)
            else:
                print("bestmove 0000", flush=True)

        elif cmd == "quit":
            break

        elif cmd == "d":
            # Debug: print the board
            print(board, flush=True)
            print(f"FEN: {board.fen()}", flush=True)


def _parse_position(tokens: list[str]) -> chess.Board:
    """Parse a 'position' UCI command and return the resulting board."""
    board = chess.Board()
    idx = 1

    if tokens[idx] == "startpos":
        idx += 1
    elif tokens[idx] == "fen":
        idx += 1
        fen_parts = []
        while idx < len(tokens) and tokens[idx] != "moves":
            fen_parts.append(tokens[idx])
            idx += 1
        board = chess.Board(" ".join(fen_parts))

    # Apply moves if present
    if idx < len(tokens) and tokens[idx] == "moves":
        idx += 1
        while idx < len(tokens):
            board.push_uci(tokens[idx])
            idx += 1

    return board


def _parse_go_depth(tokens: list[str]) -> int:
    """Parse depth from 'go' command. Default to depth 3."""
    for i, token in enumerate(tokens):
        if token == "depth" and i + 1 < len(tokens):
            return int(tokens[i + 1])
        if token == "movetime" and i + 1 < len(tokens):
            # Rough mapping: more time = more depth
            ms = int(tokens[i + 1])
            if ms < 100:
                return 2
            elif ms < 1000:
                return 3
            elif ms < 5000:
                return 4
            else:
                return 5
    # Default depth for go with time controls
    return 3


if __name__ == "__main__":
    main()
